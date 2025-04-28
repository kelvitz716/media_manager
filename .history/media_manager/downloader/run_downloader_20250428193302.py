"""Script to run only the Telegram downloader component."""
import asyncio
import os
import sys
import signal
from typing import Any
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from common.config_manager import ConfigManager
from common.logger_setup import setup_logging
from common.notification_service import NotificationService
from downloader.bot import TelegramDownloader

async def main() -> None:
    """Main entry point for downloader."""
    # Load configuration
    config_manager = ConfigManager("config.json")
    config = config_manager.config
    
    # Set up logging
    logger = setup_logging(config["logging"], "TelegramDownloader")
    
    # Initialize notification service
    notification = NotificationService(config["notification"])
    
    # Initialize downloader
    downloader = TelegramDownloader(config, notification)
    
    def handle_shutdown(signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        asyncio.create_task(downloader.stop())
        
    # Set up signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handle_shutdown)
    
    try:
        # Ensure download directory exists
        os.makedirs(config["paths"]["telegram_download_dir"], exist_ok=True)
        
        # Start downloader
        await downloader.start()
        
    except Exception as e:
        logger.error(f"Error running downloader: {e}")
        await downloader.stop()

if __name__ == "__main__":
    asyncio.run(main())