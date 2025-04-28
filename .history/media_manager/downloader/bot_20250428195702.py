"""Telegram downloader bot module."""
import asyncio
import os
import aiofiles
from typing import Dict, Any, Optional
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
        self.bot = AsyncTeleBot(self.config["downloader"]["bot_token"])
        
        # Initialize Telethon client for downloads
        self.client = TelegramClient(
            'media_downloader',
            self.config["downloader"]["api_id"],
            self.config["downloader"]["api_hash"]
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
        file_info = None
        
        if message.document:
            file_info = message.document
        elif message.video:
            file_info = message.video
            
        if not file_info:
            await self.bot.reply_to(message, "Unsupported media type")
            return
            
        async with self.rate_limiter:
            async with self._download_lock:
                if file_info.file_id in self._active_downloads:
                    await self.bot.reply_to(
                        message, 
                        "This file is already being downloaded"
                    )
                    return
                    
                self._active_downloads[file_info.file_id] = {
                    'progress': 0,
                    'filename': file_info.file_name
                }
            
            try:
                downloaded_path = await self._download_file(message, file_info)
                if downloaded_path:
                    await self.bot.reply_to(
                        message,
                        f"Download complete: {file_info.file_name}"
                    )
                else:
                    await self.bot.reply_to(
                        message,
                        f"Failed to download: {file_info.file_name}"
                    )
            except Exception as e:
                logger.error(f"Error processing media: {e}")
                await self.bot.reply_to(
                    message,
                    f"Error processing {file_info.file_name}: {str(e)}"
                )
                async with self._download_lock:
                    if file_info.file_id in self._active_downloads:
                        del self._active_downloads[file_info.file_id]

    async def _download_file(self, message: Message, file_info: Any) -> Optional[str]:
        """Download a file using Telethon."""
        try:
            # Prepare download path
            download_dir = self.config["paths"]["telegram_download_dir"]
            os.makedirs(download_dir, exist_ok=True)
            
            file_path = os.path.join(download_dir, file_info.file_name)
            temp_path = f"{file_path}.part"
            
            # Get the message through Telethon
            telethon_message = await self.client.get_messages(
                message.chat.id,
                ids=message.message_id
            )
            
            if not telethon_message or not telethon_message.media:
                raise ValueError("Could not find media in message")

            # Download with progress callback
            total_size = file_info.file_size
            downloaded_size = 0

            async def progress_callback(current, total):
                nonlocal downloaded_size
                if total:
                    progress = (current / total) * 100
                    self._active_downloads[file_info.file_id]['progress'] = progress
                    
                    # Update speed limit
                    chunk_size = current - downloaded_size
                    if chunk_size > 0:
                        await self.speed_limiter.limit(chunk_size)
                    downloaded_size = current
                    
                    # Notify progress periodically
                    if progress % 10 < 1:  # Update every ~10%
                        await self.notification.notify(
                            f"Downloading {file_info.file_name}: {progress:.1f}%",
                            level="progress"
                        )

            # Download using Telethon
            await self.client.download_media(
                telethon_message.media,
                temp_path,
                progress_callback=progress_callback
            )

            # Rename temp file to final name
            os.rename(temp_path, file_path)
            
            # Clean up tracking
            async with self._download_lock:
                del self._active_downloads[file_info.file_id]
            
            await self.notification.notify(
                f"Download complete: {file_info.file_name}",
                level="success"
            )
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            await self.notification.notify(
                f"Error downloading {file_info.file_name}: {str(e)}",
                level="error"
            )
            
            # Clean up failed download
            if os.path.exists(temp_path):
                os.remove(temp_path)
            async with self._download_lock:
                if file_info.file_id in self._active_downloads:
                    del self._active_downloads[file_info.file_id]
            
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