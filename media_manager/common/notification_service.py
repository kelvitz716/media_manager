"""Notification service module."""
import asyncio
import logging
import os
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
        self.logger = logging.getLogger("NotificationService")
        self.bot = None
        self.application = None
        self._token_lock = asyncio.Lock()
        self._running = False
        self._stop_event = asyncio.Event()
        self._responses = {}
        self._command_handlers = {}

    async def acquire_token(self, service_name: str) -> bool:
        """Acquire the bot token lock for a service.
        
        Args:
            service_name: Name of the service requesting the token
        Returns:
            True if token was acquired, False if timeout
        """
        try:
            self.logger.debug(f"{service_name} waiting to acquire bot token...")
            await asyncio.wait_for(self._token_lock.acquire(), timeout=30)
            self.logger.debug(f"{service_name} acquired bot token")
            return True
        except asyncio.TimeoutError:
            self.logger.warning(f"{service_name} failed to acquire bot token (timeout)")
            return False

    def release_token(self, service_name: str) -> None:
        """Release the bot token lock.
        
        Args:
            service_name: Name of the service releasing the token
        """
        if self._token_lock.locked():
            self._token_lock.release()
            self.logger.debug(f"{service_name} released bot token")

    async def start(self) -> None:
        """Start the notification service."""
        if not self.config["notification"]["enabled"]:
            self.logger.info("Notification service is disabled")
            return

        if self.config["notification"]["method"] != "telegram":
            self.logger.info("Non-telegram notification method configured")
            return

        self._running = True
        await self._initialize_bot()

    async def stop(self) -> None:
        """Stop the notification service."""
        self.logger.info("Stopping notification service")
        self._running = False
        self._stop_event.set()
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
            self.application = None
        
        if self.bot:
            self.bot = None

    async def _initialize_bot(self) -> None:
        """Initialize Telegram bot if configured."""
        if not self.config["telegram"]["enabled"]:
            self.logger.warning("Telegram is disabled in config")
            return

        bot_token = self.config["telegram"]["bot_token"]
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
            
            # Add command handlers
            for command, handler in self._command_handlers.items():
                self.application.add_handler(CommandHandler(command, handler))

            # Add message response handler
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
        """Manually poll for updates."""
        self.logger.debug("Started update polling loop")
        last_update_id = 0
        
        while self._running and not self._stop_event.is_set():
            try:
                async with self._token_lock:
                    if self.bot:
                        updates = await self.bot.get_updates(
                            offset=last_update_id + 1,
                            timeout=30
                        )
                        
                        if updates:
                            for update in updates:
                                if update.update_id > last_update_id:
                                    last_update_id = update.update_id
                                    if self.application:
                                        await self.application.process_update(update)
                                        
                await asyncio.sleep(1)  # Prevent tight loop
                
            except Exception as e:
                self.logger.error(f"Error polling updates: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on errors

    async def notify(self, message: str, level: str = "info", wait_response: bool = False, 
                    response_timeout: float = 300, file_path: str = None) -> Optional[str]:
        """Send notification and optionally wait for response."""
        if not self.bot:
            self.logger.warning("Cannot send notification: Telegram not configured")
            return None

        try:
            # Format message with emoji and file path if provided
            emoji = {
                "info": "ℹ️",
                "success": "✅",  
                "warning": "⚠️",
                "error": "❌",
                "progress": "🔄"
            }.get(level, "ℹ️")
            
            formatted_message = f"{emoji} {message}"
            if file_path:
                formatted_message += f"\nPath: {os.path.abspath(file_path)}"

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
        if replied_msg_id in self._responses:
            future = self._responses[replied_msg_id]
            if not future.done():
                future.set_result(update.message.text)

    async def wait_for_response(self, message_id: int, timeout: float = 300) -> Optional[str]:
        """Wait for response to a specific message."""
        if not self.bot:
            self.logger.warning("Cannot wait for response: Telegram not configured")
            return None

        future = asyncio.get_event_loop().create_future()
        self._responses[message_id] = future

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            self.logger.debug(f"Response timeout for message {message_id}")
            return None
        finally:
            self._responses.pop(message_id, None)

    async def register_command(self, command: str, handler: Callable[[Update, Any], Awaitable[None]]) -> None:
        """Register a command handler."""
        self._command_handlers[command] = handler
        
        if self.application:
            self.application.add_handler(CommandHandler(command, handler))
            self.logger.debug(f"Registered command handler for /{command}")

    async def notify_all(self, messages: list[str], wait_responses: bool = False, response_timeout: float = 300) -> list[Optional[str]]:
        """Send multiple notifications and wait for responses."""
        responses = []
        for message in messages:
            response = await self.notify(message, wait_response=wait_responses, response_timeout=response_timeout)
            responses.append(response)
        return responses

    async def ensure_token_and_notify(self, service_name: str, message: str, level: str = "info", 
                                    wait_response: bool = False, response_timeout: float = 300,
                                    file_path: str = None) -> Optional[str]:
        """Acquire token, send notification, and release token."""
        if await self.acquire_token(service_name):
            try:
                result = await self.notify(message, level, wait_response, response_timeout, file_path)
                return result
            finally:
                self.release_token(service_name)
        return None