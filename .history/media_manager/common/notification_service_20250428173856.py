"""Notification service module."""
import asyncio
import logging
from typing import Any, Dict, Optional, Callable, Awaitable, List
from telegram.ext import Application, CommandHandler
from telegram import Bot, Update

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
            # Start update polling
            self._update_task = asyncio.create_task(self._poll_updates())
            await self.bot.get_me()  # Test the connection
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self.bot = None

    async def _poll_updates(self) -> None:
        """Poll for updates from Telegram."""
        last_update_id = 0
        while self.running:
            try:
                updates = await self.bot.get_updates(offset=last_update_id + 1, timeout=30)
                for update in updates:
                    if update.message and update.message.reply_to_message:
                        await self.handle_update(update)
                    if update.update_id >= last_update_id:
                        last_update_id = update.update_id
            except Exception as e:
                logger.error(f"Error polling updates: {e}")
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the notification service."""
        self.running = False
        if hasattr(self, '_update_task'):
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        if self.bot:
            await self.bot.close()
            self.bot = None

    async def notify(self, message: str, wait_response: bool = False, response_timeout: float = 300) -> Optional[str]:
        """Send notification and optionally wait for response."""
        if not self.bot:
            logger.warning("Cannot send notification: Telegram not configured")
            return None

        try:
            chat_id = self.config["notification"]["chat_id"]
            sent_message = await self.bot.send_message(
                chat_id=chat_id,
                text=message
            )
            
            if wait_response:
                return await self.wait_for_response(sent_message.message_id, timeout=response_timeout)
            return None

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return None

    async def notify_all(self, messages: List[str], wait_responses: bool = False, response_timeout: float = 300) -> List[Optional[str]]:
        """Send multiple notifications and wait for responses."""
        return await asyncio.gather(*[
            self.notify(msg, wait_responses, response_timeout) 
            for msg in messages
        ])

    async def wait_for_response(self, message_id: int, timeout: float = 300) -> Optional[str]:
        """Wait for response to a specific message."""
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

    async def handle_update(self, update: Update) -> None:
        """Handle incoming update from Telegram."""
        if not update.message or not update.message.reply_to_message:
            return

        replied_msg_id = update.message.reply_to_message.message_id
        if replied_msg_id in self._waiting_responses:
            self._handle_response(replied_msg_id, update.message.text)

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