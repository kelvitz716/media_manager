"""Notification service for media manager."""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from telebot.async_telebot import AsyncTeleBot
from .rate_limiters import AsyncRateLimiter

class NotificationService:
    """Handles notifications and user interactions."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize notification service.
        
        Args:
            config: Notification configuration
        """
        self.config = config
        self.logger = logging.getLogger("NotificationService")
        
        # Initialize bot if telegram is configured
        self.bot = None
        self.chat_id = None
        if self.config.get("method") == "telegram":
            bot_token = config.get("bot_token")
            if bot_token:
                self.bot = AsyncTeleBot(bot_token)
                self.chat_id = config.get("chat_id")
                
        # Set up rate limiter for notifications
        self.rate_limiter = AsyncRateLimiter()
        
        # Callback registry for commands and responses
        self._callbacks: Dict[str, Callable] = {}
        
        # Response waiting registry
        self._waiting_for_response: Dict[int, asyncio.Future] = {}
        
    async def notify(self, message: str, level: str = "info", reply_to: Optional[int] = None) -> None:
        """
        Send a notification.
        
        Args:
            message: Notification message
            level: Notification level (info/warning/error/success/progress)
            reply_to: Optional message ID to reply to
        """
        try:
            # Add emoji based on level
            emoji = {
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
                "success": "✅",
                "progress": "🔄"
            }.get(level, "")
            
            formatted_message = f"{emoji} {message}"
            
            if self.bot and self.chat_id:
                # Rate limit notifications
                await self.rate_limiter.wait_if_needed(f"notify_{self.chat_id}")
                
                kwargs = {"chat_id": self.chat_id, "text": formatted_message}
                if reply_to:
                    kwargs["reply_to_message_id"] = reply_to
                    
                await self.bot.send_message(**kwargs)
            else:
                # Fallback to logging
                log_func = getattr(self.logger, level if level != "success" else "info")
                log_func(message)
                
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            
    async def wait_for_response(self, prompt: str, timeout: int = 60) -> Optional[str]:
        """
        Send a prompt and wait for user response.
        
        Args:
            prompt: Message to send
            timeout: Seconds to wait for response
            
        Returns:
            User response or None on timeout
        """
        if not self.bot or not self.chat_id:
            self.logger.warning("Cannot wait for response: Telegram not configured")
            return None
            
        try:
            # Send prompt
            message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=prompt
            )
            
            # Create future for response
            response_future = asyncio.Future()
            self._waiting_for_response[message.message_id] = response_future
            
            try:
                # Wait for response with timeout
                return await asyncio.wait_for(response_future, timeout)
                
            except asyncio.TimeoutError:
                await self.notify(
                    "Response timeout - operation cancelled",
                    level="warning",
                    reply_to=message.message_id
                )
                return None
                
            finally:
                # Clean up
                self._waiting_for_response.pop(message.message_id, None)
                
        except Exception as e:
            self.logger.error(f"Error waiting for response: {e}")
            return None
            
    async def register_command(self, command: str, callback: Callable) -> None:
        """
        Register a command callback.
        
        Args:
            command: Command to register
            callback: Function to call when command is received
        """
        if not self.bot:
            return
            
        try:
            self._callbacks[command] = callback
            
            # Set up command handler
            @self.bot.message_handler(commands=[command])
            async def handle_command(message):
                try:
                    await callback(message)
                except Exception as e:
                    self.logger.error(f"Error in command handler: {e}")
                    await self.notify(
                        f"Error processing command: {str(e)}",
                        level="error",
                        reply_to=message.message_id
                    )
                    
        except Exception as e:
            self.logger.error(f"Failed to register command {command}: {e}")
            
    def handle_response(self, message_id: int, text: str) -> None:
        """
        Handle incoming response.
        
        Args:
            message_id: ID of message being responded to
            text: Response text
        """
        future = self._waiting_for_response.get(message_id)
        if future and not future.done():
            future.set_result(text)
            
    async def start(self) -> None:
        """Start notification service."""
        if self.bot:
            await self.bot.delete_webhook(drop_pending_updates=True)
            asyncio.create_task(self.bot.polling(non_stop=True))
            self.logger.info("Started notification service")
            
    async def stop(self) -> None:
        """Stop notification service."""
        if self.bot:
            await self.bot.close_session()
            self.logger.info("Stopped notification service")