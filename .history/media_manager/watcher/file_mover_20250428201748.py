"""File system watcher for processing downloaded media."""
import os
import asyncio
import logging
from typing import Dict, Any, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watcher.categorizer import MediaCategorizer
from common.notification_service import NotificationService

class MediaFileHandler(FileSystemEventHandler):
    """Handles file system events for media files."""
    
    def __init__(self, categorizer: MediaCategorizer, loop: asyncio.AbstractEventLoop):
        """Initialize file handler."""
        self.categorizer = categorizer
        self.logger = logging.getLogger("MediaFileHandler")
        self._processing_files: Set[str] = set()
        self._processing_lock = asyncio.Lock()
        self._loop = loop
        
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            asyncio.run_coroutine_threadsafe(
                self._handle_new_file(event.src_path),
                self._loop
            )
            
    async def _handle_new_file(self, file_path: str) -> None:
        """Process newly created file."""
        try:
            # Check if file is already being processed
            async with self._processing_lock:
                if file_path in self._processing_files:
                    return
                self._processing_files.add(file_path)
            
            try:
                # Wait for file to be fully written
                await self._wait_for_file_ready(file_path)
                
                # Process file
                success = await self.categorizer.process_file(file_path)
                if not success:
                    await self.categorizer.move_to_unmatched(file_path)
                    
            finally:
                # Remove from processing set
                async with self._processing_lock:
                    self._processing_files.remove(file_path)
                    
        except Exception as e:
            self.logger.error(f"Error handling new file {file_path}: {e}")
            
    async def _wait_for_file_ready(self, file_path: str, timeout: int = 300) -> None:
        """
        Wait for file to be fully written.
        
        Args:
            file_path: Path to file
            timeout: Maximum seconds to wait
        """
        start_time = asyncio.get_event_loop().time()
        last_size = -1
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                current_size = os.path.getsize(file_path)
                if current_size == last_size and current_size > 0:
                    # File size hasn't changed, assume it's complete
                    return
                last_size = current_size
            except OSError:
                # File might be temporarily locked
                pass
                
            await asyncio.sleep(1)
            
        raise TimeoutError(f"Timeout waiting for file {file_path} to be ready")

class MediaWatcher:
    """Watches download directory for new media files."""
    
    def __init__(self, config_manager, notification_service: NotificationService, categorizer: MediaCategorizer = None):
        """
        Initialize watcher.
        
        Args:
            config_manager: Configuration manager instance
            notification_service: Notification service instance
            categorizer: Optional MediaCategorizer instance for testing
        """
        self.config_manager = config_manager
        self.logger = logging.getLogger("MediaWatcher")
        self.notification = notification_service
        self._loop = asyncio.get_event_loop()
        
        # Initialize components
        self.categorizer = categorizer if categorizer is not None else MediaCategorizer(config_manager, notification_service)
        self.handler = MediaFileHandler(self.categorizer, self._loop)
        self.observer = Observer()
        
    async def start(self) -> None:
        """Start watching for new files."""
        watch_dir = self.config_manager["paths"]["telegram_download_dir"]
        
        if not os.path.exists(watch_dir):
            os.makedirs(watch_dir)
            
        self.observer.schedule(self.handler, watch_dir, recursive=False)
        self.observer.start()
        self.logger.info(f"Started watching directory: {watch_dir}")
        
        # Process existing files if configured
        if self.config_manager["download"].get("process_existing_files", False):
            for filename in os.listdir(watch_dir):
                file_path = os.path.join(watch_dir, filename)
                if os.path.isfile(file_path):
                    asyncio.create_task(self.handler._handle_new_file(file_path))
            
    def stop(self) -> None:
        """Stop watching for new files."""
        self.observer.stop()
        self.observer.join()
        self.logger.info("Stopped watching for new files")