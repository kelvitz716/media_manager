"""Notification service module."""
import asyncio
import logging
from typing import Any, Dict, Optional, Callable, Awaitable
from telegram.ext import Application, CommandHandler
from telegram import Bot

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications and handling responses."""

    def __init__(self, config_manager):
        """Initialize notification service."""
        self.config = config_manager
        self.bot = None
        self._waiting_responses = {}
        self._command_handlers = {}
        self.running = False

    async def start(self) -> None:
        """Start the notification service."""
        if self.config["notification"]["enabled"]:
            await self._initialize_bot()
        self.running = True

    async def stop(self) -> None:
        """Stop the notification service."""
        self.running = False
        if self.bot:
            await self.bot.close()
            self.bot = None

    async def _initialize_bot(self) -> None:
        """Initialize Telegram bot if configured."""
        if self.config["notification"]["method"] != "telegram":
            return

        bot_token = self.config["notification"]["bot_token"]
        if not bot_token:
            logger.warning("Telegram bot token not configured")
            return

        try:
            self.bot = Bot(token=bot_token)
            await self.bot.get_me()  # Test the connection
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self.bot = None

    async def notify(self, message: str, level: str = "info", wait_response: bool = False, response_timeout: float = 300) -> Optional[str]:
        """Send notification and optionally wait for response."""
        if not self.bot:
            logger.warning("Cannot send notification: Telegram not configured")
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

            chat_id = self.config["notification"]["chat_id"]
            sent_message = await self.bot.send_message(
                chat_id=chat_id,
                text=formatted_message
            )
            
            if wait_response:
                return await self.wait_for_response(sent_message.message_id, timeout=response_timeout)
            return None

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return None

    async def notify_all(self, messages: list[str], wait_responses: bool = False, response_timeout: float = 300) -> list[Optional[str]]:
        """
        Send multiple notifications and optionally wait for responses.
        
        Args:
            messages: List of messages to send
            wait_responses: Whether to wait for responses
            response_timeout: Maximum time to wait for each response in seconds
            
        Returns:
            List of response texts if wait_responses is True, list of None otherwise
        """
        responses = []
        for message in messages:
            response = await self.notify(message, wait_responses, response_timeout)
            responses.append(response)
        return responses

    async def wait_for_response(self, message_id: int, timeout: float = 300) -> Optional[str]:
        """
        Wait for response to a specific message.
        
        Args:
            message_id: ID of message to wait for response to
            timeout: Maximum time to wait in seconds
            
        Returns:
            Response text or None if timeout
        """
        if not self.bot:
            logger.warning("Cannot wait for response: Telegram not configured")
            return None

        future = asyncio.get_event_loop().create_future()
        self._waiting_responses[message_id] = future

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            logger.debug(f"Response timeout for message {message_id}")
            return None
        finally:
            self._waiting_responses.pop(message_id, None)

    async def handle_update(self, update: Any) -> None:
        """Handle incoming update from Telegram."""
        if not update.message or not update.message.reply_to_message:
            return

        replied_msg_id = update.message.reply_to_message.message_id
        if replied_msg_id in self._waiting_responses:
            future = self._waiting_responses[replied_msg_id]
            if not future.done():
                future.set_result(update.message.text)

    def _handle_response(self, message_id: int, text: str) -> None:
        """Handle response to a message."""
        if message_id in self._waiting_responses:
            future = self._waiting_responses[message_id]
            if not future.done():
                future.set_result(text)

    async def register_command(self, command: str, handler: Callable[[str], Awaitable[None]]) -> None:
        """Register a command handler."""
        self._command_handlers[command] = handler

    async def _handle_command(self, command: str, args: str) -> None:
        """Handle a received command."""
        if command in self._command_handlers:
            await self._command_handlers[command](args)
        else:
            logger.warning(f"Unknown command: {command}")