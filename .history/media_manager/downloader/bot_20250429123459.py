"""Telegram downloader bot module."""
import asyncio
import os
from typing import Dict, Any, Optional, Tuple
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message
import logging
from telethon import TelegramClient
from telethon.tl.types import Document, DocumentAttributeFilename
from media_manager.common.notification_service import NotificationService
from media_manager.common.rate_limiters import AsyncRateLimiter, SpeedLimiter

logger = logging.getLogger(__name__)

class TelegramDownloader:
    """Handles downloading media from Telegram."""

    def __init__(self, config_manager, notification_service: NotificationService):
        """Initialize the downloader."""
        self.config = config_manager
        self.notification = notification_service
        self.bot = AsyncTeleBot(self.config["telegram"]["bot_token"])
        
        # Initialize Telethon client for downloads
        self.client = TelegramClient(
            'telegram_bot_session',
            api_id=int(self.config["telegram"]["api_id"]),
            api_hash=self.config["telegram"]["api_hash"]
        )
        
        self.rate_limiter = AsyncRateLimiter(
            self.config["download"]["max_concurrent_downloads"]
        )
        self.speed_limiter = SpeedLimiter(
            self.config["download"]["speed_limit"]
        )
        self._active_downloads = {}
        self._download_lock = asyncio.Lock()
        self._setup_handlers()

    async def start(self) -> None:
        """Start the bot and client."""
        self.logger.info("Starting Telegram downloader")
        self.logger.debug("Initializing Telethon client")
        # Start with bot token instead of interactive auth
        await self.client.start(bot_token=self.config["telegram"]["bot_token"])
        self.logger.debug("Starting bot polling")
        await self.bot.infinity_polling()
        
    async def stop(self) -> None:
        """Stop the bot and client."""
        self.logger.info("Stopping Telegram downloader")
        self.logger.debug("Disconnecting Telethon client")
        await self.client.disconnect()
        self.logger.debug("Closing bot session")
        await self.bot.close_session()