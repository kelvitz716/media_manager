"""Telegram bot and downloader implementation."""
from typing import Dict, Any, List
import asyncio
import os
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename
from media_manager.common.notification_service import NotificationService
from media_manager.common.rate_limiters import AsyncRateLimiter, SpeedLimiter
from media_manager.downloader.download_task import DownloadManager, DownloadTask

class TelegramBot:
    """Handles interactions with the Telegram Bot API."""
    
    def __init__(self, config_manager, notification_service: NotificationService):
        """Initialize the Telegram bot."""
        self.config = config_manager.config
        self.notification = notification_service
        self.bot = AsyncTeleBot(self.config["telegram"]["bot_token"])
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Set up message handlers."""
        @self.bot.message_handler(commands=['start', 'help'])
        async def send_welcome(message):
            await self.bot.reply_to(message, 
                "Welcome to Media Manager Bot!\n\n"
                "Commands:\n"
                "/help - Show this help message\n"
                "/status - Show system status\n"
                "/queue - Show download queue\n"
                "/settings - Show current settings"
            )
            
        @self.bot.message_handler(commands=['status'])
        async def send_status(message):
            # This would be improved with actual status info
            await self.bot.reply_to(message, "System is running normally")
        
        @self.bot.message_handler(commands=['queue'])
        async def send_queue(message):
            # This would be improved with actual queue info
            await self.bot.reply_to(message, "No downloads in queue")
        
        @self.bot.message_handler(commands=['settings'])
        async def send_settings(message):
            settings_text = (
                "Current Settings:\n"
                f"Download directory: {self.config['download']['directory']}\n"
                f"Max concurrent downloads: {self.config['download']['max_concurrent_downloads']}\n"
                f"Speed limit: {self.config['download']['speed_limit']} KB/s"
            )
            await self.bot.reply_to(message, settings_text)
    
    async def start(self):
        """Start the bot."""
        await self.bot.polling(non_stop=True, skip_pending=True)
        
    async def stop(self):
        """Stop the bot."""
        await self.bot.stop_polling()


class TelegramDownloader:
    """Handles downloading media from Telegram."""

    def __init__(self, config_manager, notification_service: NotificationService):
        """Initialize the downloader."""
        self.config = config_manager
        self.notification = notification_service
        self.bot = AsyncTeleBot(self.config.config["telegram"]["bot_token"])
        self.download_dir = self.config.config["paths"]["telegram_download_dir"]
        
        # Initialize Telethon client for downloads
        self.client = TelegramClient(
            'telegram_bot_session',
            api_id=int(self.config.config["telegram"]["api_id"]),
            api_hash=self.config.config["telegram"]["api_hash"]
        )
        
        # Create rate limiters
        self.rate_limiter = AsyncRateLimiter(
            self.config.config["download"]["max_concurrent_downloads"]
        )
        self.speed_limiter = SpeedLimiter(
            self.config.config["download"]["speed_limit"]
        )
        
        # Initialize download manager
        self.download_manager = DownloadManager(config_manager, notification_service)
        
        # Initialize state variables
        self._active_downloads = {}
        self._download_queue = []
        self._download_lock = asyncio.Lock()
        self._running = False
        
        # Set up message handlers
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Set up message handlers for the bot."""
        @self.bot.message_handler(content_types=['document', 'video', 'audio', 'photo'])
        async def handle_media(message):
            """Handle incoming media messages."""
            try:
                await self.download_manager.process_media_message(message)
                await self.bot.reply_to(message, 
                    f"Media received and added to download queue.\n"
                    f"Current queue: {self.download_manager.get_queue_status()}"
                )
            except Exception as e:
                await self.bot.reply_to(message, f"Failed to process media: {str(e)}")
                await self.notification.notify(
                    f"Error processing media message: {str(e)}",
                    level="error"
                )
        
        @self.bot.message_handler(commands=['queue'])
        async def show_queue(message):
            """Show current download queue status."""
            queue_status = self.download_manager.get_queue_status()
            active_downloads = self.download_manager.get_active_downloads()
            
            response = ["📥 Download Queue Status:\n"]
            
            if active_downloads:
                response.append("🔄 ACTIVE DOWNLOADS:")
                for i, dl in enumerate(active_downloads, 1):
                    response.append(
                        f"{i}. {os.path.basename(dl['filename'])}\n"
                        f"   Progress: {dl['progress']:.1f}% - {dl['status']}"
                    )
            
            response.append(f"\n{queue_status}")
            
            await self.bot.reply_to(message, "\n".join(response))
        
        @self.bot.message_handler(commands=['cancel'])
        async def cancel_download(message):
            """Cancel active download."""
            # This would need implementation based on how you track active downloads
            await self.bot.reply_to(message, "This feature is not yet implemented.")
        
    async def start(self):
        """Start the downloader and bot."""
        self._running = True
        await self.client.start()
        
        # Start the bot in a separate task
        asyncio.create_task(self.bot.polling(non_stop=True, skip_pending=True))
        
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Send startup notification
        await self.notification.notify(
            "TelegramDownloader service started successfully",
            level="info"
        )
    
    async def stop(self):
        """Stop the downloader and bot."""
        self._running = False
        await self.bot.stop_polling()
        await self.client.disconnect()
        
        # Send shutdown notification
        await self.notification.notify(
            "TelegramDownloader service stopped",
            level="info"
        )

    async def download_file(self, file_id, chat_id, message_id):
        """Download a file using Telethon client."""
        # This is a placeholder implementation
        # In a real implementation, you would:
        # 1. Get the message from Telegram
        # 2. Download the file with progress reporting
        # 3. Update the task status
        pass

    async def get_stats(self) -> Dict[str, Any]:
        """Get current download statistics."""
        active_downloads = self.download_manager.get_active_downloads()
        
        # Get basic stats from download manager
        queue_size = len(self._download_queue)
        total = len(active_downloads) + queue_size
        
        return {
            'total': total,
            'active': len(active_downloads),
            'queued': queue_size,
            'speed_limit': self.speed_limiter.limit if self.speed_limiter else None,
        }

    async def get_queue_status(self) -> List[Dict[str, Any]]:
        """Get status of queued downloads."""
        # This should return more detailed information about the queue
        # Placeholder implementation
        queue_items = []
        for dl in self.download_manager.get_active_downloads():
            queue_items.append({
                'file_name': os.path.basename(dl['filename']),
                'size': 0,  # This would be populated with actual size
                'added_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'priority': 'normal',
                'progress': dl['progress'],
                'status': dl['status']
            })
        return queue_items