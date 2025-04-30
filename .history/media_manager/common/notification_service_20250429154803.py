"""Notification service module."""
import asyncio
import logging
from typing import Any, Dict, Optional, Callable, Awaitable
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, Updater
from telegram import Update

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications and handling responses."""

    def __init__(self, config_manager):
        """Initialize notification service."""
        self.config = config_manager.config
        self.config_manager = config_manager  # Keep for backwards compatibility
        self.bot = None
        self.application = None
        self._waiting_responses = {}
        self._command_handlers = {}
        self._running = False
        self._stop_event = asyncio.Event()
        self.logger = logging.getLogger("NotificationService")

    async def start(self) -> None:
        """Start the notification service."""
        self.logger.info("Starting notification service")
        if self.config["notification"]["enabled"]:
            await self._initialize_bot()
        self._running = True

    async def stop(self) -> None:
        """Stop the notification service."""
        self.logger.info("Stopping notification service")
        self._running = False
        self._stop_event.set()
        
        if self.application:
            self.logger.debug("Stopping application polling")
            await self.application.stop()
            self.logger.debug("Shutting down application")
            await self.application.shutdown()
            self.application = None
        
        if self.bot:
            self.logger.debug("Cleaning up bot instance")
            self.bot = None

    async def _initialize_bot(self) -> None:
        """Initialize Telegram bot if configured."""
        if self.config["notification"]["method"] != "telegram":
            return

        bot_token = self.config["notification"]["bot_token"]
        if not bot_token:
            self.logger.warning("Telegram bot token not configured")
            return

        try:
            self.logger.debug("Creating bot application")
            builder = Application.builder()
            builder.token(bot_token)
            # Disable updater for manual polling
            builder.updater(None)
            self.application = builder.build()
            self.bot = self.application.bot

            # Add handlers
            self.logger.debug("Setting up message handlers")
            self.application.add_handler(MessageHandler(
                filters.REPLY & filters.TEXT,
                self._handle_message_response
            ))

            # Initialize and start application
            self.logger.debug("Initializing application")
            await self.application.initialize()
            self.logger.debug("Starting application")
            await self.application.start()
            
            # Start manual polling in background
            self.logger.debug("Starting manual update polling")
            asyncio.create_task(self._poll_updates())

        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}", exc_info=True)
            if self.application:
                await self.application.shutdown()
            self.bot = None
            self.application = None

    async def _poll_updates(self) -> None:
        """Manually poll for updates to avoid HTTPXRequest issues."""
        self.logger.debug("Started update polling loop")
        while self._running and not self._stop_event.is_set():
            try:
                # Get updates with small timeout
                self.logger.debug("Polling for updates")
                updates = await self.bot.get_updates(timeout=5)
                
                # Process updates
                if updates:
                    self.logger.debug(f"Processing {len(updates)} updates")
                    for update in updates:
                        await self.application.process_update(update)
                
                # Small delay to prevent tight loop
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error polling updates: {e}", exc_info=True)
                await asyncio.sleep(5)  # Longer delay on error
                
        self.logger.debug("Update polling loop stopped")

    async def notify(self, message: str, level: str = "info", wait_response: bool = False, response_timeout: float = 300) -> Optional[str]:
        """Send notification and optionally wait for response."""
        if not self.bot:
            self.logger.warning("Cannot send notification: Telegram not configured")
            return None

        try:
            # Format message with emoji based on level
            emoji = {
                "info": "ℹ️",
                "success": "✅",  
                "warning": "⚠️",
                "error": "❌",
                "progress": "🔄"
            }.get(level, "ℹ️")
            
            formatted_message = f"{emoji} {message}"

            self.logger.debug(f"Sending notification: {formatted_message}")
            chat_id = self.config["notification"]["chat_id"]
            sent_message = await self.bot.send_message(
                chat_id=chat_id,
                text=formatted_message
            )
            
            self.logger.debug(f"Notification sent successfully (Message ID: {sent_message.message_id})")
            
            if wait_response:
                return await self.wait_for_response(sent_message.message_id, timeout=response_timeout)
            return None

        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}", exc_info=True)
            return None

    async def _handle_message_response(self, update: Update, context: Any) -> None:
        """Handle message responses."""
        if not update.message or not update.message.reply_to_message:
            return

        replied_msg_id = update.message.reply_to_message.message_id
        if replied_msg_id in self._waiting_responses:
            future = self._waiting_responses[replied_msg_id]
            if not future.done():
                future.set_result(update.message.text)

    async def wait_for_response(self, message_id: int, timeout: float = 300) -> Optional[str]:
        """Wait for response to a specific message."""
        if not self.bot:
            self.logger.warning("Cannot wait for response: Telegram not configured")
            return None

        future = asyncio.get_event_loop().create_future()
        self._waiting_responses[message_id] = future

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            self.logger.debug(f"Response timeout for message {message_id}")
            return None
        finally:
            self._waiting_responses.pop(message_id, None)

    async def register_command(self, command: str, handler: Callable[[Update, Any], Awaitable[None]]) -> None:
        """Register a command handler."""
        if not self.application:
            self.logger.warning("Cannot register command: Bot not initialized")
            return
            
        self.application.add_handler(CommandHandler(command, handler))

    async def notify_all(self, messages: list[str], wait_responses: bool = False, response_timeout: float = 300) -> list[Optional[str]]:
        """Send multiple notifications and wait for responses."""
        responses = []
        for message in messages:
            response = await self.notify(message, wait_response=wait_responses, response_timeout=response_timeout)
            responses.append(response)
        return responses