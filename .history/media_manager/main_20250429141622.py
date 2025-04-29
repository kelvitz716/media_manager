"""Main entry point for the media manager."""
import asyncio
import logging
from media_manager.common.config_manager import ConfigManager
from media_manager.common.notification_service import NotificationService
from media_manager.common.logger_setup import setup_logging
from media_manager.watcher.categorizer import MediaCategorizer
from media_manager.downloader.bot import TelegramDownloader

async def main():
    """Main async entry point."""
    # Initialize config
    config_manager = ConfigManager()
    
    # Setup logging
    setup_logging(config_manager)
    logger = logging.getLogger(__name__)
    logger.info("Starting Media Manager")
    
    # Initialize notification service
    notification_service = NotificationService(config_manager)
    
    # Initialize media categorizer
    categorizer = MediaCategorizer(config_manager, notification_service)
    
    # Initialize and start downloader
    downloader = TelegramDownloader(config_manager, notification_service, categorizer)
    
    # Start background workers
    logger.info("Starting background workers")
    asyncio.create_task(downloader.start())
    
    try:
        # Keep the main task running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await downloader.stop()
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
        await downloader.stop()
        raise

if __name__ == "__main__":
    asyncio.run(main())