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
        self._command_handlers = {}
        self._polling_task = None
        self._polling_interval = 1.0  # 1 second polling interval
        self._media_handler = None

    def register_command(self, command: str, handler: Callable[[Update, Any], Awaitable[None]]) -> None:
        """Register a command handler."""
        self.logger.debug(f"Registering command handler for /{command}")
        self._command_handlers[command] = handler

    def register_media_handler(self, handler: Callable[[Update, Any], Awaitable[None]]) -> None:
        """Register handler for media files."""
        self.logger.debug("Registering media file handler")
        self._media_handler = handler

    async def start(self) -> None:
        """Start the notification service."""
        if not self.config["telegram"]["enabled"]:
            self.logger.info("Telegram notifications are disabled")
            return

        await self._initialize_bot()

    async def stop(self) -> None:
        """Stop the notification service."""
        self.logger.info("Stopping notification service")
        
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        
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

            # Register handlers
            self.logger.debug("Setting up message handlers")
            # Register command handlers
            for command, handler in self._command_handlers.items():
                self.application.add_handler(CommandHandler(command, handler))

            # Add message response handler
            self.application.add_handler(MessageHandler(
                filters.REPLY & filters.TEXT,
                self._handle_message_response
            ))

            # Add media file handler
            if self._media_handler:
                self.application.add_handler(MessageHandler(
                    filters.Document.ALL | filters.VIDEO | filters.AUDIO,
                    self._media_handler
                ))

            # Initialize and start application
            self.logger.debug("Initializing application")
            await self.application.initialize()
            self.logger.debug("Starting application")
            await self.application.start()
            
            # Start manual polling in background
            self.logger.debug("Starting manual update polling")
            self._polling_task = asyncio.create_task(self._poll_updates())
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}", exc_info=True)
            if self.application:
                await self.application.shutdown()
            self.bot = None
            self.application = None
            raise

    async def _poll_updates(self) -> None:
        """Poll for updates manually."""
        offset = 0
        while True:
            try:
                updates = await self.bot.get_updates(offset=offset, timeout=30)
                for update in updates:
                    offset = update.update_id + 1
                    await self.application.process_update(update)
            except Exception as e:
                self.logger.error(f"Error polling updates: {e}")
                await asyncio.sleep(self._polling_interval)
            await asyncio.sleep(0.1)  # Small delay between polls

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
            
        reply_to = update.message.reply_to_message.message_id
        if reply_to in self._responses:
            future = self._responses[reply_to]
            if not future.done():
                future.set_result(update.message)

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