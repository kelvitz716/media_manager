"""Script to run only the file watcher component."""
import asyncio
import os
import sys
import signal
from typing import Any
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from media_manager.common.config_manager import ConfigManager
from media_manager.common.logger_setup import setup_logging
from media_manager.common.notification_service import NotificationService
from media_manager.watcher.file_mover import MediaWatcher

async def main() -> None:
    """Main entry point for watcher."""
    # Load configuration
    config_manager = ConfigManager("config.json")
    config = config_manager.config
    
    # Set up logging
    logger = setup_logging(config["logging"], "MediaWatcher")
    
    # Initialize notification service
    notification = NotificationService(config["notification"])
    
    # Initialize watcher
    watcher = MediaWatcher(config, notification)
    
    def handle_shutdown(signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        watcher.stop()
        asyncio.get_event_loop().stop()
        
    # Set up signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handle_shutdown)
    
    try:
        # Ensure required directories exist
        for path in config["paths"].values():
            os.makedirs(path, exist_ok=True)
        
        # Start watcher
        watcher.start()
        
        # Run event loop
        loop = asyncio.get_event_loop()
        loop.run_forever()
        
    except Exception as e:
        logger.error(f"Error running watcher: {e}")
        watcher.stop()
    finally:
        loop = asyncio.get_event_loop()
        loop.close()

if __name__ == "__main__":
    asyncio.run(main())