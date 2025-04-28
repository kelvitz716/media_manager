"""Main entry point for Media Manager."""
import asyncio
import os
import signal
from typing import Dict, Any
import logging
from common.config_manager import ConfigManager
from media_manager.common.logger_setup import setup_logging
from media_manager.common.notification_service import NotificationService
from media_manager.downloader.bot import TelegramDownloader
from media_manager.watcher.file_mover import MediaWatcher

class MediaManager:
    """Coordinates media downloading and processing components."""
    
    def __init__(self):
        """Initialize Media Manager."""
        # Load configuration
        self.config_manager = ConfigManager("config.json")
        self.config = self.config_manager.config
        
        # Set up logging
        self.logger = setup_logging(self.config["logging"])
        
        # Initialize notification service
        self.notification = NotificationService(self.config["notification"])
        
        # Initialize components
        self.downloader = TelegramDownloader(self.config, self.notification)
        self.watcher = MediaWatcher(self.config, self.notification)
        
        # Set up signal handlers
        self._setup_signal_handlers()
        
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
        try:
            # Stop components
            await self.downloader.stop()
            self.watcher.stop()
            
            # Stop event loop
            loop = asyncio.get_running_loop()
            loop.stop()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        
    async def start(self) -> None:
        """Start all components."""
        try:
            # Ensure directories exist
            for path in self.config["paths"].values():
                os.makedirs(path, exist_ok=True)
            
            # Start components
            self.watcher.start()
            await self.downloader.start()
            
        except Exception as e:
            self.logger.error(f"Error starting Media Manager: {e}")
            await self._shutdown()

def main() -> None:
    """Main entry point."""
    manager = MediaManager()
    
    # Run event loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(manager.start())
        loop.run_forever()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
    finally:
        loop.close()

if __name__ == "__main__":
    main()