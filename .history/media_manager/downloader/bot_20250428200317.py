"""Telegram downloader bot module."""
import asyncio
import os
import aiofiles
from typing import Dict, Any, Optional, Tuple
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message
import logging
from telethon import TelegramClient
from telethon.tl.types import Document, DocumentAttributeFilename
from common.notification_service import NotificationService
from common.rate_limiters import AsyncRateLimiter, SpeedLimiter

logger = logging.getLogger(__name__)

class TelegramDownloader:
    """Handles downloading media from Telegram."""

    def __init__(self, config_manager, notification_service: NotificationService):
        """Initialize the downloader."""
        self.config = config_manager
        self.notification = notification_service
        self.logger = logging.getLogger("TelegramDownloader")
        
        # Initialize telegram-bot-api for commands and notifications
        self.bot = AsyncTeleBot(self.config["downloader"]["bot_token"])
        
        # Initialize Telethon client for downloads
        self.client = TelegramClient(
            'media_downloader',
            int(self.config["downloader"]["api_id"]),  # api_id must be int
            self.config["downloader"]["api_hash"]
        )
        
        # Set up limiters
        self.rate_limiter = AsyncRateLimiter(
            self.config["download"]["max_concurrent_downloads"]
        )
        self.speed_limiter = SpeedLimiter(
            self.config["download"]["speed_limit"]
        )
        
        # Track downloads
        self._active_downloads = {}
        self._download_lock = asyncio.Lock()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up bot message handlers."""
        @self.bot.message_handler(content_types=['document', 'video'])
        async def handle_media(message: Message):
            await self._process_media(message)
            
        @self.bot.message_handler(commands=['start'])
        async def start(message: Message):
            await self.bot.reply_to(message, "Media Manager Bot is ready!")
            
        @self.bot.message_handler(commands=['status'])
        async def status(message: Message):
            status_text = "Active downloads:\n"
            if self._active_downloads:
                for file_id, info in self._active_downloads.items():
                    progress = info.get('progress', 0)
                    filename = info.get('filename', 'Unknown')
                    status_text += f"📥 {filename}: {progress:.1f}%\n"
            else:
                status_text += "No active downloads"
            await self.bot.reply_to(message, status_text)

    async def _process_media(self, message: Message) -> None:
        """Process incoming media message."""
        try:
            # Get file info from message
            file_id = message.document.file_id if message.document else message.video.file_id
            file_info = await self.bot.get_file(file_id)
            
            # Get filename
            if message.document and message.document.file_name:
                filename = message.document.file_name
            elif message.video and message.video.file_name:
                filename = message.video.file_name
            else:
                filename = f"{file_id}.mp4"  # Default for videos
            
            # Initialize download tracking
            async with self._download_lock:
                self._active_downloads[file_id] = {
                    'progress': 0,
                    'filename': filename,
                    'total_size': file_info.file_size
                }
            
            # Download using Telethon for better performance
            await self.notification.send(f"Starting download of {filename}")
            filepath = await self._download_file(message, file_info)
            
            if filepath:
                await self.notification.send(f"Successfully downloaded {filename}")
            else:
                await self.notification.send(f"Failed to download {filename}")
                
        except Exception as e:
            self.logger.error(f"Error processing media: {str(e)}", exc_info=True)
            await self.notification.send(f"Error downloading file: {str(e)}")
        finally:
            async with self._download_lock:
                if file_id in self._active_downloads:
                    del self._active_downloads[file_id]

    async def _download_file(self, message: Message, file_info: Any) -> Optional[str]:
        """Download a file using Telethon."""
        file_id = message.document.file_id if message.document else message.video.file_id
        info = self._active_downloads[file_id]
        filename = info['filename']
        
        # Ensure download directory exists
        download_dir = self.config["paths"]["telegram_download_dir"]
        os.makedirs(download_dir, exist_ok=True)
        filepath = os.path.join(download_dir, filename)
        
        try:
            # Get message through Telethon
            telethon_message = await self.client.get_messages(
                message.chat.id,
                ids=message.message_id
            )
            
            # Download using Telethon with progress tracking
            async def progress_callback(received_bytes, total):
                if total:
                    percentage = (received_bytes / total) * 100
                    async with self._download_lock:
                        self._active_downloads[file_id]['progress'] = percentage

            await self.client.download_media(
                telethon_message,
                filepath,
                progress_callback=progress_callback
            )
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Download error: {str(e)}", exc_info=True)
            return None

    async def start(self) -> None:
        """Start the bot and client."""
        self.logger.info("Starting Telegram downloader")
        await self.client.start()
        await self.bot.infinity_polling()
        
    async def stop(self) -> None:
        """Stop the bot and client."""
        self.logger.info("Stopping Telegram downloader")
        await self.client.disconnect()
        await self.bot.close_session()