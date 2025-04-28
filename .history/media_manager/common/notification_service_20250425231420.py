"""Unified notification and command handling service."""
import asyncio
import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from telebot.async_telebot import AsyncTeleBot
from .rate_limiters import AsyncRateLimiter

class NotificationService:
    """Handles notifications and command interactions."""
    
    def __init__(self, config: Dict[str, Any], bot: AsyncTeleBot = None):
        """
        Initialize notification service.
        
        Args:
            config: Notification configuration
            bot: Optional AsyncTeleBot instance
        """
        self.config = config
        self.logger = logging.getLogger("NotificationService")
        self.enabled = config.get("enabled", False)
        self.bot = bot
        self.chat_id = config.get("chat_id")
        self.rate_limiter = AsyncRateLimiter()
        self._command_handlers = {}
        self._response_futures = {}

    async def notify(self, message: str, level: str = "info", chat_id: str = None) -> None:
        """Send a notification."""
        if not self.enabled:
            return

        try:
            # Use provided chat_id or fallback to default
            target_chat = chat_id or self.chat_id
            if not target_chat:
                self.logger.warning("No chat_id configured for notifications")
                return

            # Apply rate limiting
            await self.rate_limiter.wait_if_needed(f"notify_{target_chat}")

            # Format message based on level
            emoji_map = {
                "info": "ℹ️",
                "success": "✅",
                "warning": "⚠️",
                "error": "❌",
                "progress": "🔄"
            }
            emoji = emoji_map.get(level, "ℹ️")
            formatted_msg = f"{emoji} {message}"

            if self.bot:
                await self.bot.send_message(target_chat, formatted_msg, parse_mode="HTML")
            else:
                print(formatted_msg)

        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")

    def register_command(self, command: str, handler: Callable[..., Awaitable[None]]) -> None:
        """Register a command handler."""
        self._command_handlers[command] = handler

    async def handle_command(self, command: str, *args, **kwargs) -> None:
        """Handle a received command."""
        if command in self._command_handlers:
            try:
                await self._command_handlers[command](*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error handling command {command}: {e}")
                await self.notify(f"Error executing command: {str(e)}", "error")

    async def wait_for_response(self, prompt: str, timeout: int = 60) -> Optional[str]:
        """
        Wait for a user response to a prompt.
        
        Args:
            prompt: Prompt message to send
            timeout: Timeout in seconds
            
        Returns:
            User response or None if timed out
        """
        if not self.enabled or not self.bot:
            return None

        try:
            # Create a future for the response
            future = asyncio.Future()
            chat_id = str(self.chat_id)
            self._response_futures[chat_id] = future

            # Send prompt
            await self.notify(prompt)

            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(future, timeout)
                return response
            except asyncio.TimeoutError:
                await self.notify("Response timeout. Please try again.", "warning")
                return None
            finally:
                # Clean up
                if chat_id in self._response_futures:
                    del self._response_futures[chat_id]

        except Exception as e:
            self.logger.error(f"Error waiting for response: {e}")
            return None

    def set_response(self, chat_id: str, text: str) -> None:
        """Set a response for a waiting prompt."""
        chat_id = str(chat_id)
        if chat_id in self._response_futures and not self._response_futures[chat_id].done():
            self._response_futures[chat_id].set_result(text)