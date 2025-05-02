"""Main application module."""
import asyncio
import logging
import os

from media_manager.common.config_manager import ConfigManager
from media_manager.common.notification_service import NotificationService
from media_manager.downloader.bot import TelegramBot, TelegramDownloader
from media_manager.watcher.categorizer import MediaCategorizer

class MediaManager:
    """Main application class."""

    def __init__(self):
        """Initialize the application."""
        self.logger = logging.getLogger("MediaManager")
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
        self.config_manager = ConfigManager(config_path)
        self.notification_service = NotificationService(self.config_manager)
        self.media_categorizer = MediaCategorizer(self.config_manager, self.notification_service)
        
        # Initialize Telegram components
        self.telegram_downloader = TelegramDownloader(self.config_manager, self.notification_service)
        self.telegram_bot = TelegramBot(self.telegram_downloader, self.notification_service)

    async def start(self):
        """Start the application."""
        try:
            # First start notification service
            await self.notification_service.start()
            
            # Then start downloader which uses Telethon
            await self.telegram_downloader.start()
            
            # Register media handler from downloader
            self.notification_service.register_media_handler(self.telegram_downloader._handle_download_command)
            
            self.logger.info("Media Manager started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start Media Manager: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop the application."""
        self.logger.info("Stopping Media Manager")
        
        # Stop in reverse order
        await self.telegram_downloader.stop()
        await self.notification_service.stop()

async def main():
    """Main entry point."""
    media_manager = MediaManager()
    await media_manager.start()
    
    try:
        # Keep the application running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await media_manager.stop()

if __name__ == "__main__":
    asyncio.run(main())