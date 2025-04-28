"""File system watcher for processing downloaded media."""
import os
import asyncio
import logging
from typing import Dict, Any, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from media_manager.watcher.categorizer import MediaCategorizer
from media_manager.common.notification_service import NotificationService

class MediaFileHandler(FileSystemEventHandler):
    """Handles file system events for media files."""
    
    def __init__(self, categorizer: MediaCategorizer):
        """
        Initialize file handler.
        
        Args:
            categorizer: Media categorizer instance
        """
        self.categorizer = categorizer
        self.logger = logging.getLogger("MediaFileHandler")
        self._processing_files: Set[str] = set()
        self._processing_lock = asyncio.Lock()
        
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            asyncio.create_task(self._handle_new_file(event.src_path))
            
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
    
    def __init__(self, config: Dict[str, Any], notification_service: NotificationService, categorizer: MediaCategorizer = None):
        """
        Initialize watcher.
        
        Args:
            config: Application configuration
            notification_service: Notification service instance
            categorizer: Optional MediaCategorizer instance for testing
        """
        self.config = config
        self.logger = logging.getLogger("MediaWatcher")
        self.notification = notification_service
        
        # Initialize components
        self.categorizer = categorizer if categorizer is not None else MediaCategorizer(config, notification_service)
        self.handler = MediaFileHandler(self.categorizer)
        self.observer = Observer()
        
    def start(self) -> None:
        """Start watching for new files."""
        watch_dir = self.config["paths"]["telegram_download_dir"]
        
        if not os.path.exists(watch_dir):
            os.makedirs(watch_dir)
            
        self.observer.schedule(self.handler, watch_dir, recursive=False)
        self.observer.start()
        self.logger.info(f"Started watching directory: {watch_dir}")
        
        # Process existing files if configured
        if self.config.get("process_existing_files", False):
            asyncio.create_task(self._process_existing_files())
            
    def stop(self) -> None:
        """Stop watching for new files."""
        self.observer.stop()
        self.observer.join()
        self.logger.info("Stopped watching for new files")
        
    async def _process_existing_files(self) -> None:
        """Process any existing files in watch directory."""
        watch_dir = self.config["paths"]["telegram_download_dir"]
        
        try:
            for filename in os.listdir(watch_dir):
                file_path = os.path.join(watch_dir, filename)
                if os.path.isfile(file_path):
                    await self.handler._handle_new_file(file_path)
                    
        except Exception as e:
            self.logger.error(f"Error processing existing files: {e}")