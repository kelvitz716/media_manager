"""Main entry point for the media manager."""
import asyncio
import logging
import os
import signal
from typing import Any
from pathlib import Path
from media_manager.common.config_manager import ConfigManager
from media_manager.common.notification_service import NotificationService
from media_manager.common.logger_setup import setup_logging
from media_manager.watcher.categorizer import MediaCategorizer
from media_manager.downloader.bot import TelegramDownloader

class MediaManager:
    def __init__(self):
        """Initialize Media Manager."""
        # Load configuration
        self.config_manager = ConfigManager("config.json")
        self.config = self.config_manager.config
        
        # Set up logging
        self.logger = setup_logging(self.config["logging"])
        
        # Ensure directories exist with correct permissions
        self._ensure_directories()
        
        # Initialize notification service with token locking
        self.notification = NotificationService(self.config_manager)
        
        # Initialize components
        self.categorizer = None
        self.downloader = None
        
        # Set up signal handlers
        self._setup_signal_handlers()
        
    def _ensure_directories(self):
        """Create necessary directories with correct permissions."""
        required_dirs = [
            self.config["paths"]["telegram_download_dir"],
            self.config["paths"]["movies_dir"],
            self.config["paths"]["tv_shows_dir"],
            self.config["paths"]["unmatched_dir"],
            self.config["paths"]["temp_download_dir"]
        ]
        
        for dir_path in required_dirs:
            if not dir_path:
                continue
            try:
                # Convert to absolute path
                abs_path = os.path.abspath(dir_path)
                # Create with correct permissions for external access
                os.makedirs(abs_path, mode=0o755, exist_ok=True)
                self.logger.info(f"Ensured directory exists: {abs_path}")
            except OSError as e:
                self.logger.error(f"Failed to create directory {dir_path}: {e}")
                raise
                
    def _setup_signal_handlers(self) -> None:
        """Set up handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._handle_shutdown)
            
    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        self.logger.info("Shutdown signal received")
        asyncio.create_task(self._shutdown())
        
    async def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.logger.info("Starting graceful shutdown")
        
        if self.downloader:
            self.logger.info("Stopping downloader...")
            await self.downloader.stop()
            
        if self.categorizer:
            self.logger.info("Stopping categorizer...")
            await self.notification.ensure_token_and_notify(
                "MediaManager",
                "Shutting down media manager...",
                level="info"
            )
            
        await self.notification.stop()
        self.logger.info("Shutdown complete")

    async def start(self) -> None:
        """Start the media manager services."""
        try:
            # Start notification service first
            await self.notification.start()
            
            # Initialize and start media categorizer
            self.categorizer = MediaCategorizer(self.config_manager, self.notification)
            
            # Initialize and start downloader
            self.downloader = TelegramDownloader(self.config_manager, self.notification)
            await self.downloader.start()
            
            self.logger.info("Media Manager started successfully")
            
        except Exception as e:
            self.logger.error(f"Error starting services: {e}", exc_info=True)
            await self._shutdown()
            raise

async def main():
    """Main async entry point."""
    # Initialize Media Manager
    media_manager = MediaManager()
    logger = logging.getLogger(__name__)
    
    try:
        # Start all services
        await media_manager.start()
        
        # Keep the main task running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await media_manager._shutdown()
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        await media_manager._shutdown()
        raise

if __name__ == "__main__":
    asyncio.run(main())