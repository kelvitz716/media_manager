"""Telegram downloader bot module."""
import asyncio
import os
import time
import datetime
from typing import Dict, Any, Optional
from telebot.async
from telebot.types import Message
import logging
from telethon import TelegramClient
from telethon.tl.types import Document

from media_manager.common.notification_service import NotificationService
from media_manager.common.rate_limiters import AsyncRateLimiter, SpeedLimiter
from media_manager.downloader.download_task import DownloadTask

logger = logging.getLogger(__name__)

class TelegramDownloader:
    """Handles downloading media from Telegram."""
    
    def __init__(self, config: Dict[str, Any], notification_service: NotificationService, categorizer):
        self.config = config
        self.notification = notification_service
        self.categorizer = categorizer
        self.logger = logger
        
        # Initialize bot and client
        self.bot = AsyncTeleBot(self.config.get_value("telegram.bot_token"))
        self.client = TelegramClient(
            'telegram_bot_session',
            api_id=int(self.config.get_value("telegram.api_id")),
            api_hash=self.config.get_value("telegram.api_hash")
        )
        
        # Initialize queues and tracking
        self.download_queue = asyncio.Queue()
        self.active_downloads: Dict[str, DownloadTask] = {}
        self._download_lock = asyncio.Lock()
        
        # Initialize rate limiters
        self.rate_limiter = AsyncRateLimiter(
            self.config.get_value("download.max_concurrent_downloads")
        )
        self.speed_limiter = SpeedLimiter(
            self.config.get_value("download.speed_limit")
        )
        
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
            if not self.active_downloads and self.download_queue.empty():
                await self.bot.reply_to(message, "No active downloads")
                return
                
            status_text = []
            
            # Active downloads
            if self.active_downloads:
                status_text.append("📥 Active downloads:")
                for task in self.active_downloads.values():
                    status_text.append(task.get_status_text())
                    
            # Queued downloads
            if not self.download_queue.empty():
                status_text.append(f"\n📋 Queued files: {self.download_queue.qsize()}")
                
            await self.bot.reply_to(message, "\n".join(status_text))
            
    async def _process_media(self, message: Message) -> None:
        """Process incoming media message and add to download queue."""
        try:
            # Get file info
            file_id = message.document.file_id if message.document else message.video.file_id
            filename = (
                message.document.file_name if message.document and message.document.file_name
                else message.video.file_name if message.video and message.video.file_name
                else f"{file_id}.mp4"
            )
            
            self.logger.info(f"Processing media: {filename} (ID: {file_id})")
            
            # Check if already downloading
            if file_id in self.active_downloads:
                await self.bot.reply_to(message, "⚠️ This file is already being downloaded!")
                return
                
            # Send initial status message
            status_msg = await self.bot.reply_to(
                message,
                f"📋 Added to download queue: {filename}\n"
                f"Position: {self.download_queue.qsize() + 1}"
            )
            
            # Create download task
            task = DownloadTask(
                file_id=file_id,
                filename=filename,
                chat_id=message.chat.id,
                message_id=message.message_id,
                status_message_id=status_msg.message_id
            )
            
            # Add to queue
            await self.download_queue.put(task)
            self.logger.debug(f"Added {filename} to download queue")
            
        except Exception as e:
            self.logger.error(f"Error processing media: {str(e)}", exc_info=True)
            await self.notification.notify(f"Error queuing file: {str(e)}", level="error")
            
    async def _process_download_task(self, task: DownloadTask) -> None:
        """Process a single download task."""
        try:
            # Update task status
            task.status = "downloading"
            await self._update_status_message(task)
            
            # Get message through Telethon
            telethon_message = await self.client.get_messages(
                task.chat_id,
                ids=task.message_id
            )
            
            # Set up download path
            download_dir = self.config["paths"]["telegram_download_dir"]
            os.makedirs(download_dir, exist_ok=True)
            task.download_path = os.path.join(download_dir, task.filename)
            
            # Track download progress
            async def progress_callback(received_bytes: int, total: int) -> None:
                task.update_progress(received_bytes, total)
                await self._update_status_message(task)
            
            # Perform download
            await self.client.download_media(
                telethon_message,
                task.download_path,
                progress_callback=progress_callback
            )
            
            # Update status to complete
            task.status = "completed"
            await self._update_status_message(task)
            
            # Notify completion
            await self.notification.notify(
                f"Download completed: {task.filename}",
                level="success"
            )
            
            # Start categorization
            await self.categorizer.process_file(task.download_path)
            
        except Exception as e:
            self.logger.error(f"Error downloading {task.filename}: {str(e)}", exc_info=True)
            task.status = "error"
            await self._update_status_message(task)
            await self.notification.notify(f"Error downloading file: {str(e)}", level="error")
            
        finally:
            # Clean up tracking
            async with self._download_lock:
                if task.file_id in self.active_downloads:
                    del self.active_downloads[task.file_id]
                    
    async def _update_status_message(self, task: DownloadTask) -> None:
        """Update the status message for a download task."""
        if not task.status_message_id:
            return
            
        try:
            await self.bot.edit_message_text(
                task.get_status_text(),
                task.chat_id,
                task.status_message_id
            )
        except Exception as e:
            self.logger.debug(f"Failed to update status message: {e}")
            
    async def _download_worker(self) -> None:
        """Process downloads from the queue."""
        while True:
            try:
                # Get next task
                task = await self.download_queue.get()
                
                # Add to active downloads
                async with self._download_lock:
                    self.active_downloads[task.file_id] = task
                    
                # Process with rate limiting
                async with self.rate_limiter:
                    await self._process_download_task(task)
                    
                self.download_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in download worker: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on error
                
    async def start(self) -> None:
        """Start the bot and workers."""
        self.logger.info("Starting Telegram downloader")
        
        # Start download worker
        asyncio.create_task(self._download_worker())
        
        # Start Telethon client
        self.logger.debug("Starting Telethon client")
        await self.client.start(bot_token=self.config["telegram"]["bot_token"])
        
        # Start bot polling
        self.logger.debug("Starting bot polling")
        await self.bot.infinity_polling()
        
    async def stop(self) -> None:
        """Stop the bot and client."""
        self.logger.info("Stopping Telegram downloader")
        
        # Wait for queue to empty
        if not self.download_queue.empty():
            self.logger.info("Waiting for download queue to empty...")
            await self.download_queue.join()
            
        # Close connections
        self.logger.debug("Disconnecting Telethon client")
        await self.client.disconnect()
        self.logger.debug("Closing bot session")
        await self.bot.close_session()