"""Main entry point for Media Manager."""
import asyncio
import os
import signal
import sys
import time
from typing import Dict, Any
import logging
from media_manager.common.config_manager import ConfigManager
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
        
        # State tracking
        self._force_shutdown = False
        self._shutting_down = False
        self._shutdown_start = 0
        
        # Set up signal handlers
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self) -> None:
        """Set up handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
            
    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        if self._shutting_down:
            if time.time() - self._shutdown_start < 2:  # Within 2 seconds of first Ctrl+C
                self.logger.warning("Force shutdown triggered")
                self._force_shutdown = True
                sys.exit(1)  # Force exit
            return
            
        self._shutting_down = True
        self._shutdown_start = time.time()
        self.logger.info("Shutdown signal received, gracefully shutting down...")
        asyncio.create_task(self._shutdown())
        
    async def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        try:
            # Stop components with timeout
            shutdown_complete = asyncio.create_task(self._shutdown_components())
            try:
                await asyncio.wait_for(shutdown_complete, timeout=10.0)  # 10 second timeout
            except asyncio.TimeoutError:
                self.logger.error("Shutdown timed out")
                
            # Stop event loop
            loop = asyncio.get_running_loop()
            loop.stop()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            if self._force_shutdown:
                sys.exit(1)
                
    async def _shutdown_components(self) -> None:
        """Shutdown components with proper cleanup."""
        try:
            # Stop components in parallel
            shutdown_tasks = [
                self.downloader.stop(),
                self.watcher.stop()
            ]
            await asyncio.gather(*shutdown_tasks)
        except Exception as e:
            self.logger.error(f"Error stopping components: {e}")
            
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
    loop.create_task(manager.start())
    
    try:
        loop.run_forever()
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        loop.close()

if __name__ == "__main__":
    main()