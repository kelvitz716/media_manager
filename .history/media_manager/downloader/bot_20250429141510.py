"""Telegram downloader bot module."""
import asyncio
import os
import time
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
    
    def __init__(self, config, notification_service, categorizer):
        """Initialize the downloader."""
        self.config = config
        self.notification = notification_service
        self.logger = logger  # Use module-level logger
        self.bot = AsyncTeleBot(self.config["telegram"]["bot_token"])
        self.categorizer = categorizer
        self.download_queue = asyncio.Queue()
        
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
                    
    async def start(self):
        """Start the download worker."""
        asyncio.create_task(self._download_worker())
        
    async def _download_worker(self):
        """Process downloads from queue."""
        while True:
            try:
                task = await self.download_queue.get()
                await self._process_download_task(task)
                self.download_queue.task_done()
            except Exception as e:
                self.logger.error(f"Error in download worker: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on error
                
    async def _process_media(self, message: Message) -> None:
        """Process incoming media message."""
        try:
            # Get file info from message
            file_id = message.document.file_id if message.document else message.video.file_id
            
            # Get filename
            if message.document and message.document.file_name:
                filename = message.document.file_name
            elif message.video and message.video.file_name:
                filename = message.video.file_name
            else:
                filename = f"{file_id}.mp4"  # Default for videos
            
            self.logger.info(f"Processing media: {filename} (ID: {file_id})")
            
            # Check if already downloading
            if file_id in self._active_downloads:
                await self.bot.reply_to(message, "⚠️ This file is already being downloaded!")
                return
                
            # Initialize download tracking
            async with self._download_lock:
                self._active_downloads[file_id] = {
                    'progress': 0,
                    'filename': filename,
                    'start_time': time.time(),
                    'bytes_downloaded': 0,
                    'speed': 0
                }
            
            # Send initial status message
            status_msg = await self.bot.reply_to(
                message, 
                f"📋 Added to download queue: {filename}\n"
                f"Position: {self.download_queue.qsize() + 1}"
            )
            
            # Create download task
            task = {
                'file_id': file_id,
                'message': message,
                'filename': filename,
                'status_msg': status_msg,
                'chat_id': message.chat.id
            }
            
            # Add to queue
            await self.download_queue.put(task)
            
        except Exception as e:
            self.logger.error(f"Error processing media: {str(e)}", exc_info=True)
            await self.notification.notify(f"Error queuing file: {str(e)}", level="error")

    async def _process_download_task(self, task):
        """Process a download task from the queue."""
        file_id = task['file_id']
        message = task['message']
        filename = task['filename']
        status_msg = task['status_msg']
        
        try:
            # Update status to downloading
            await self.bot.edit_message_text(
                f"📥 Starting download: {filename}",
                status_msg.chat.id,
                status_msg.message_id
            )
            
            # Get message through Telethon
            telethon_message = await self.client.get_messages(
                message.chat.id,
                ids=message.message_id
            )
            
            # Download file
            download_dir = self.config["paths"]["telegram_download_dir"]
            os.makedirs(download_dir, exist_ok=True)
            filepath = os.path.join(download_dir, filename)
            
            # Track download progress
            start_time = time.time()
            last_update_time = 0
            last_bytes = 0
            
            async def progress_callback(received_bytes, total):
                if total:
                    nonlocal last_update_time, last_bytes
                    current_time = time.time()
                    
                    # Update progress every 2 seconds
                    if current_time - last_update_time >= 2:
                        # Calculate speed
                        elapsed = current_time - start_time
                        speed = received_bytes / elapsed if elapsed > 0 else 0
                        
                        # Calculate ETA
                        remaining_bytes = total - received_bytes
                        eta = remaining_bytes / speed if speed > 0 else 0
                        
                        percentage = (received_bytes / total) * 100
                        async with self._download_lock:
                            self._active_downloads[file_id].update({
                                'progress': percentage,
                                'bytes_downloaded': received_bytes,
                                'speed': speed,
                                'eta': eta
                            })
                        
                        # Update status message
                        progress_text = (
                            f"📥 Downloading: {filename}\n"
                            f"Progress: {percentage:.1f}%\n"
                            f"Size: {received_bytes/(1024*1024):.1f}/{total/(1024*1024):.1f} MB\n"
                            f"Speed: {speed/1024/1024:.1f} MB/s\n"
                            f"ETA: {datetime.timedelta(seconds=int(eta))}"
                        )
                        
                        try:
                            await self.bot.edit_message_text(
                                progress_text,
                                status_msg.chat.id,
                                status_msg.message_id
                            )
                        except Exception as e:
                            self.logger.debug(f"Failed to update progress message: {e}")
                            
                        last_update_time = current_time
                        last_bytes = received_bytes
            
            # Perform download
            await self.client.download_media(
                telethon_message,
                filepath,
                progress_callback=progress_callback
            )
            
            # Download complete
            download_time = time.time() - start_time
            completion_text = (
                f"✅ Download Complete: {filename}\n"
                f"Time taken: {datetime.timedelta(seconds=int(download_time))}\n\n"
                f"Starting media categorization..."
            )
            
            await self.bot.edit_message_text(
                completion_text,
                status_msg.chat.id,
                status_msg.message_id
            )
            
            # Notify completion
            await self.notification.notify(
                f"Download completed: {filename}",
                level="success"
            )
            
            # Now trigger categorization
            await self.categorizer.process_file(filepath)
                
        except Exception as e:
            self.logger.error(f"Error downloading {filename}: {str(e)}", exc_info=True)
            await self.notification.notify(f"Error downloading file: {str(e)}", level="error")
            if status_msg:
                await self.bot.edit_message_text(
                    f"❌ Error downloading {filename}:\n{str(e)}",
                    status_msg.chat.id,
                    status_msg.message_id
                )
        finally:
            # Clean up tracking
            async with self._download_lock:
                if file_id in self._active_downloads:
                    del self._active_downloads[file_id]

    async def start(self) -> None:
        """Start the bot and client."""
        self.logger.info("Starting Telegram downloader")
        self.logger.debug("Initializing Telethon client")
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