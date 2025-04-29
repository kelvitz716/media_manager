"""File system watcher for processing downloaded media."""
import os
import time
import asyncio
import logging
from typing import Dict, Any, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from media_manager.watcher.categorizer import MediaCategorizer
from media_manager.common.notification_service import NotificationService
import shutil

class MediaFileHandler(FileSystemEventHandler):
    """Handles file system events for media files."""
    
    def __init__(self, categorizer: MediaCategorizer, loop: asyncio.AbstractEventLoop):
        """Initialize file handler."""
        self.categorizer = categorizer
        self.logger = logging.getLogger("MediaFileHandler")
        self._processing_files: Set[str] = set()
        self._processing_lock = asyncio.Lock()
        self._loop = loop
        self._stopping = False
        self._tasks: Set[asyncio.Task] = set()
        self._tasks_lock = asyncio.Lock()
        
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory and not self._stopping:
            self.logger.info(f"New file detected: {event.src_path}")
            future = asyncio.run_coroutine_threadsafe(
                self._create_processing_task(event.src_path),
                self._loop
            )
            future.add_done_callback(self._handle_task_result)
            
    async def _create_processing_task(self, file_path: str) -> None:
        """Create and track a new processing task."""
        try:
            async with self._tasks_lock:
                if not self._stopping:
                    task = self._loop.create_task(self._handle_new_file(file_path))
                    self._tasks.add(task)
                    task.add_done_callback(self._remove_task)
                    self.logger.debug(f"Created processing task for: {file_path}")
        except Exception as e:
            self.logger.error(f"Error creating task for {file_path}: {e}", exc_info=True)
            
    def _remove_task(self, task):
        """Remove a completed task from the set."""
        self._tasks.discard(task)
            
    def _handle_task_result(self, future):
        """Handle the result of an async task."""
        try:
            future.result()
        except Exception as e:
            self.logger.error(f"Error in file processing task: {e}", exc_info=True)
            
    async def _handle_new_file(self, file_path: str) -> None:
        """Process newly created file."""
        try:
            # Check if already processing
            async with self._processing_lock:
                if file_path in self._processing_files:
                    return
                self._processing_files.add(file_path)
                
            self.logger.info(f"Starting to process file: {file_path}")
            
            # Wait for file to be ready with timeout
            try:
                await self._wait_for_file_ready(file_path, timeout=30)
            except TimeoutError:
                self.logger.error(f"Timeout waiting for file to stabilize: {file_path}")
                return
            except asyncio.CancelledError:
                self.logger.info(f"Processing cancelled for file: {file_path}")
                return
                
            # Process the file
            if not self._stopping:
                try:
                    success = await self.categorizer.process_file(file_path)
                    if not success:
                        await self.categorizer.move_to_unmatched(file_path)
                except Exception as e:
                    self.logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
                    await self.categorizer.move_to_unmatched(file_path)
                    
        finally:
            # Remove from processing set
            async with self._processing_lock:
                self._processing_files.discard(file_path)
                self.logger.debug(f"Finished processing file: {file_path}")

    async def _wait_for_file_ready(self, file_path: str, timeout: int = 30) -> None:
        """Wait for file to be ready for processing."""
        start_time = time.time()
        last_size = -1
        last_modified = 0
        
        while time.time() - start_time < timeout:
            if self._stopping:
                raise asyncio.CancelledError()
                
            try:
                if not os.path.exists(file_path):
                    await asyncio.sleep(0.1)
                    continue
                    
                curr_size = os.path.getsize(file_path)
                curr_modified = os.path.getmtime(file_path)
                
                if curr_size == last_size and curr_modified == last_modified:
                    # File hasn't changed in 1 second
                    if time.time() - last_modified >= 1:
                        return
                else:
                    last_size = curr_size
                    last_modified = curr_modified
                    
                await asyncio.sleep(0.1)
                
            except (OSError, IOError) as e:
                self.logger.warning(f"Error checking file: {e}")
                await asyncio.sleep(0.1)
                
        raise TimeoutError(f"Timeout waiting for file to stabilize: {file_path}")
        
    async def stop(self):
        """Stop the file handler and wait for tasks to complete."""
        self._stopping = True
        
        # Cancel and wait for all tasks
        async with self._tasks_lock:
            if self._tasks:
                self.logger.info(f"Waiting for {len(self._tasks)} file processing tasks to complete...")
                # Create list of tasks to avoid RuntimeError from set changing size
                tasks = list(self._tasks)
                # Cancel all tasks
                for task in tasks:
                    task.cancel()
                # Wait for all tasks with timeout
                try:
                    await asyncio.wait(tasks, timeout=5)
                except asyncio.TimeoutError:
                    self.logger.warning("Timeout waiting for tasks to complete")
                # Clear tasks set
                self._tasks.clear()

class MediaWatcher:
    """Watches download directory for new media files."""
    
    def __init__(self, config: Dict[str, Any], notification: NotificationService):
        """Initialize watcher."""
        self.config = config
        self.notification = notification
        self.logger = logging.getLogger("MediaWatcher")
        
        # Get event loop
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
        # Initialize components
        self.categorizer = MediaCategorizer(config, notification)
        self.event_handler = MediaFileHandler(self.categorizer, self._loop)
        self.observer = Observer()
        
    def start(self) -> None:
        """Start watching directory."""
        watch_dir = self.config["paths"]["telegram_download_dir"]
        self.observer.schedule(self.event_handler, watch_dir, recursive=False)
        self.observer.start()
        self.logger.info(f"Started watching directory: {watch_dir}")
        
    async def stop(self) -> None:
        """Stop watching directory."""
        self.logger.info("Stopping file watcher")
        # Stop accepting new files first
        await self.event_handler.stop()
        # Then stop the observer
        self.observer.stop()
        self.observer.join(timeout=5)
        self.logger.info("File watcher stopped")