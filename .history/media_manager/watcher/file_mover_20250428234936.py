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
            self.logger.info(f"New file detected: {event.src_path}")
            future = asyncio.run_coroutine_threadsafe(
                self._handle_new_file(event.src_path),
                self._loop
            )
            future.add_done_callback(self._handle_task_result)
            self.logger.debug(f"Created processing task for: {event.src_path}")
            
    def _handle_task_result(self, future):
        """Handle the result of an async task."""
        try:
            future.result()
        except Exception as e:
            self.logger.error(f"Error in file processing task: {e}", exc_info=True)
            
    async def _handle_new_file(self, file_path: str) -> None:
        """Process newly created file."""
        try:
            # Check if file is already being processed
            async with self._processing_lock:
                if file_path in self._processing_files:
                    self.logger.debug(f"File already being processed: {file_path}")
                    return
                self._processing_files.add(file_path)
                self.logger.info(f"Starting categorization for: {file_path}")
            
            try:
                # Wait for file to be fully written
                self.logger.info(f"Waiting for file to stabilize: {file_path}")
                await self._wait_for_file_ready(file_path)
                
                # Process file
                self.logger.info(f"Beginning categorization process for: {file_path}")
                success = await self.categorizer.process_file(file_path)
                if success:
                    self.logger.info(f"Successfully categorized file: {file_path}")
                else:
                    self.logger.warning(f"Failed to categorize file, moving to unmatched: {file_path}")
                    await self.categorizer.move_to_unmatched(file_path)
                    
            finally:
                # Remove from processing set
                async with self._processing_lock:
                    self._processing_files.remove(file_path)
                    self.logger.info(f"Completed processing file: {file_path}")
                    
        except Exception as e:
            self.logger.error(f"Error handling new file {file_path}: {e}", exc_info=True)

class MediaWatcher:
    """Watches download directory for new media files."""
    
    def __init__(self, config_manager, notification_service: NotificationService, categorizer: MediaCategorizer = None):
        """Initialize watcher."""
        self.config_manager = config_manager
        self.logger = logging.getLogger("MediaWatcher")
        self.notification = notification_service
        
        # Get or create event loop
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        
        # Initialize components
        self.categorizer = categorizer if categorizer is not None else MediaCategorizer(config_manager, notification_service)
        self.handler = MediaFileHandler(self.categorizer, self._loop)
        self.observer = Observer()
        
    async def start(self) -> None:
        """Start watching for new files."""
        watch_dir = self.config_manager["paths"]["telegram_download_dir"]
        self.logger.info(f"Setting up watcher for directory: {watch_dir}")
        
        if not os.path.exists(watch_dir):
            os.makedirs(watch_dir)
            self.logger.debug(f"Created watch directory: {watch_dir}")
            
        self.observer.schedule(self.handler, watch_dir, recursive=False)
        self.observer.start()
        self.logger.info(f"Started watching directory: {watch_dir}")
        
        # Process existing files if configured
        if self.config_manager["download"].get("process_existing_files", False):
            self.logger.info("Processing existing files")
            for filename in os.listdir(watch_dir):
                file_path = os.path.join(watch_dir, filename)
                if os.path.isfile(file_path):
                    self.logger.debug(f"Processing existing file: {file_path}")
                    asyncio.create_task(self.handler._handle_new_file(file_path))
            
    def stop(self) -> None:
        """Stop watching for new files."""
        self.logger.info("Stopping file watcher")
        self.observer.stop()
        self.observer.join()
        self.logger.info("Stopped watching for new files")