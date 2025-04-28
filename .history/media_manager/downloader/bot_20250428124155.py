"""Telegram downloader bot module."""
import asyncio
import os
from typing import Dict, Any, Optional
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message
import logging
from .common.notification_service import NotificationService
from ..common.rate_limiters import AsyncRateLimiter, SpeedLimiter

class TelegramDownloader:
    """Handles downloading media from Telegram."""
    
    def __init__(self, config: Dict[str, Any], notification_service: NotificationService):
        """
        Initialize the downloader.
        
        Args:
            config: Bot configuration
            notification_service: Notification service instance
        """
        self.config = config
        self.logger = logging.getLogger("TelegramDownloader")
        self.notification = notification_service
        
        # Initialize bot
        self.bot = AsyncTeleBot(config["telegram"]["bot_token"])
        self.chat_id = config["telegram"].get("chat_id")
        
        # Set up rate and speed limiters
        self.rate_limiter = AsyncRateLimiter(min_interval=2.0)
        self.speed_limiter = SpeedLimiter(
            max_speed_mbps=config["download"].get("max_speed_mbps")
        )
        
        # Track active downloads
        self._active_downloads = {}
        self._download_lock = asyncio.Lock()
        
        # Register message handlers
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
            file_info = None
            if message.document:
                file_info = message.document
            elif message.video:
                file_info = message.video
                
            if not file_info:
                return
                
            # Check if we're already downloading this file
            if file_info.file_id in self._active_downloads:
                await self.bot.reply_to(
                    message, 
                    "This file is already being downloaded!"
                )
                return
                
            # Initialize download tracking
            async with self._download_lock:
                self._active_downloads[file_info.file_id] = {
                    'filename': file_info.file_name,
                    'progress': 0,
                    'size': file_info.file_size
                }
            
            # Start download
            await self._download_file(message, file_info)
            
        except Exception as e:
            self.logger.error(f"Error processing media: {e}")
            await self.notification.notify(
                f"Error processing media: {str(e)}", 
                level="error"
            )
    
    async def _download_file(self, message: Message, file_info: Any) -> Optional[str]:
        """
        Download a file from Telegram.
        
        Args:
            message: Original message
            file_info: File information object
            
        Returns:
            Downloaded file path or None on failure
        """
        try:
            # Prepare download path
            download_dir = self.config["paths"]["telegram_download_dir"]
            os.makedirs(download_dir, exist_ok=True)
            
            file_path = os.path.join(download_dir, file_info.file_name)
            temp_path = f"{file_path}.part"
            
            # Download with progress tracking
            file = await self.bot.get_file(file_info.file_id)
            downloaded_size = 0
            
            # Download in chunks
            chunk_size = self.config["download"]["chunk_size"]
            async with self.rate_limiter:
                async with open(temp_path, 'wb') as f:
                    async for chunk in self.bot.download_file(
                        file.file_path, 
                        chunk_size=chunk_size
                    ):
                        await self.speed_limiter.limit(len(chunk))
                        await f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Update progress
                        progress = (downloaded_size / file_info.file_size) * 100
                        self._active_downloads[file_info.file_id]['progress'] = progress
                        
                        # Notify progress periodically
                        if progress % 10 < (chunk_size / file_info.file_size) * 100:
                            await self.notification.notify(
                                f"Downloading {file_info.file_name}: {progress:.1f}%",
                                level="progress"
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
            self.logger.error(f"Error downloading file: {e}")
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
        """Start the bot."""
        self.logger.info("Starting Telegram downloader bot")
        await self.bot.infinity_polling()
        
    async def stop(self) -> None:
        """Stop the bot."""
        self.logger.info("Stopping Telegram downloader bot")
        await self.bot.close_session()