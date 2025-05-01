"""Download task class for managing download state and progress."""
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import datetime
import asyncio
import os

from media_manager.common.rate_limiters import RateLimiter
from media_manager.common.stats_manager import StatsManager

@dataclass
class DownloadTask:
    """Represents a download task with progress tracking."""
    
    file_id: str
    filename: str
    chat_id: int
    message_id: int
    status_message_id: Optional[int] = None
    start_time: float = field(default_factory=time.time)
    total_size: Optional[int] = None
    bytes_downloaded: int = 0
    speed: float = 0
    eta: Optional[float] = None
    status: str = "queued"
    download_path: Optional[str] = None
    last_update_time: float = field(default_factory=time.time)
    
    def update_progress(self, bytes_downloaded: int, total_size: Optional[int] = None) -> None:
        """Update download progress."""
        self.bytes_downloaded = bytes_downloaded
        if total_size:
            self.total_size = total_size
            
        # Calculate speed and ETA
        elapsed = time.time() - self.start_time
        self.speed = bytes_downloaded / elapsed if elapsed > 0 else 0
        
        if self.total_size:
            remaining_bytes = self.total_size - bytes_downloaded
            self.eta = remaining_bytes / self.speed if self.speed > 0 else None
            
    def _should_update_message(self) -> bool:
        """Determine if message should be updated based on file size and time."""
        now = time.time()
        elapsed = now - self.last_update_time
        
        # Large files (>500MB): Update every 30 minutes
        if self.total_size and self.total_size > 500 * 1024 * 1024:
            return elapsed >= 1800  # 30 minutes
            
        # Small files: Update once during download
        return elapsed >= 5  # Update after 5 seconds of starting

    @property
    def progress_percentage(self) -> float:
        """Get download progress as percentage."""
        if not self.total_size:
            return 0
        return (self.bytes_downloaded / self.total_size) * 100
        
    def get_status_text(self) -> str:
        """Get formatted status text for bot messages."""
        if self.status == "queued":
            return f"📋 Queued: {self.filename}"
            
        if self.status == "downloading":
            elapsed = time.time() - self.start_time
            is_large_file = self.total_size and self.total_size > 500 * 1024 * 1024
            
            # Format sizes
            downloaded_mb = self.bytes_downloaded / (1024 * 1024)
            total_mb = self.total_size / (1024 * 1024) if self.total_size else 0
            speed_text = f"{self.speed/1024/1024:.1f} MB/s" if self.speed >= 1024*1024 else f"{self.speed/1024:.1f} KB/s"
            
            if is_large_file:
                # Large file format
                text = [
                    "📣 STATUS UPDATE - Large download in progress",
                    f"📂 File: {self.filename}",
                    f"⏱️ Running for: {self._format_duration(elapsed)}",
                    f"✅ Progress: {self.progress_percentage:.1f}% complete",
                    f"💾 Downloaded: {downloaded_mb:.1f} MB / {total_mb:.1f} MB",
                    f"⚡ Current speed: {speed_text}",
                ]
                if self.eta:
                    hours, remainder = divmod(int(self.eta), 3600)
                    minutes, _ = divmod(remainder, 60)
                    text.append(f"🕒 ETA: {hours} h {minutes:02d} m")
                text.append("\nDownload continuing normally...")
            else:
                # Small file format
                text = [
                    "📣 STATUS UPDATE - Download in progress",
                    f"📂 File: {self.filename}",
                    f"⏱️ Running for: {self._format_duration(elapsed)}",
                    f"✅ Progress: {self.progress_percentage:.1f}% complete",
                    f"💾 Downloaded: {downloaded_mb:.1f} MB / {total_mb:.1f} MB",
                    f"⚡ Current speed: {speed_text}"
                ]
                if self.eta:
                    minutes, seconds = divmod(int(self.eta), 60)
                    text.append(f"🕒 ETA: {minutes} m {seconds:02d} s")
                    
            return "\n".join(text)
            
        if self.status == "completed":
            elapsed = time.time() - self.start_time
            avg_speed = self.total_size / elapsed if elapsed > 0 else 0
            size_mb = self.total_size / (1024 * 1024)
            
            return (
                f"✅ Download Complete!\n"
                f"📂 File: {self.filename}\n"
                f"📊 Size: {size_mb:.1f} MB\n"
                f"⏱️ Time: {self._format_duration(elapsed)}\n"
                f"🚀 Avg Speed: {avg_speed/1024:.1f} KB/s\n\n"
                f"Media categorizer will start shortly."
            )
            
        if self.status == "error":
            return (
                f"❌ Download Failed: {self.filename}\n\n"
                f"🔍 ERROR: Download could not be completed\n\n"
                f"SUGGESTIONS:\n"
                f"1️⃣ Check your internet connection\n"
                f"2️⃣ The file may be unavailable from sender\n"
                f"3️⃣ Try again later"
            )
            
        return f"Status: {self.status}"

    def _format_duration(self, seconds: float) -> str:
        """Format duration in a human-readable format."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        if minutes > 0:
            return f"{minutes}m {seconds:02d}s"
        return f"{seconds}s"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for status tracking."""
        return {
            'file_id': self.file_id,
            'filename': self.filename,
            'progress': self.progress_percentage,
            'status': self.status,
            'speed': self.speed,
            'eta': self.eta,
            'start_time': self.start_time,
            'bytes_downloaded': self.bytes_downloaded,
            'total_size': self.total_size
        }

class DownloadManager:
    """Manages downloading and processing of media files."""

    def __init__(self, config_manager, notification_service=None):
        self.config = config_manager.config
        self.notification = notification_service
        self.download_dir = self.config["paths"]["telegram_download_dir"]
        self.max_concurrent_downloads = self.config["download"]["max_concurrent_downloads"]
        self.verify_downloads = self.config["download"]["verify_downloads"]
        
        # Initialize state
        self._active_downloads = {}
        self._download_queue = asyncio.Queue()
        self._worker_tasks = set()
        self._download_lock = asyncio.Lock()
        
        # Statistics and rate limiting
        self.stats_manager = StatsManager()
        self.rate_limiter = RateLimiter()
        
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)

    async def process_media_message(self, message):
        """Process an incoming media message."""
        try:
            file_info = None
            if message.document:
                file_info = message.document
            elif message.video:
                file_info = message.video
            elif message.audio:
                file_info = message.audio
                
            if not file_info:
                raise ValueError("No supported media found in message")

            # Create download task
            task = DownloadTask(
                file_id=file_info.file_id,
                filename=os.path.join(self.download_dir, self._get_safe_filename(file_info.file_name)),
                total_size=file_info.file_size,
                chat_id=message.chat.id,
                message_id=message.message_id
            )
            
            # Add to download queue
            await self._download_queue.put(task)
            
            # Start worker if needed
            self._ensure_workers()
            
            # Send initial status
            if self.notification:
                await self.notification.notify(
                    f"Added to download queue: {task.filename}\n"
                    f"Size: {self._format_size(task.total_size)}",
                    level="info"
                )
                
        except Exception as e:
            error_msg = f"Failed to process media: {str(e)}"
            if self.notification:
                await self.notification.notify(error_msg, level="error")
            raise

    def _ensure_workers(self):
        """Ensure we have enough download workers running."""
        current_workers = len(self._worker_tasks)
        if current_workers < self.max_concurrent_downloads:
            needed = self.max_concurrent_downloads - current_workers
            for _ in range(needed):
                task = asyncio.create_task(self._download_worker())
                self._worker_tasks.add(task)
                task.add_done_callback(self._worker_tasks.discard)

    async def _download_worker(self):
        """Worker task that processes downloads from the queue."""
        while True:
            try:
                task = await self._download_queue.get()
                await self._process_download(task)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.notification:
                    await self.notification.notify(
                        f"Download worker error: {str(e)}",
                        level="error"
                    )
            finally:
                self._download_queue.task_done()

    async def _process_download(self, task: DownloadTask):
        """Process a single download task."""
        task.status = "downloading"
        task.start_time = time.time()
        self._active_downloads[task.file_id] = task
        
        try:
            # Start download with progress updates
            await self._download_file(task)
            
            if self.verify_downloads:
                await self._verify_download(task)
                
            task.status = "completed"
            task.end_time = time.time()
            
            # Update statistics
            await self.stats_manager.update(
                total_downloads=self.stats_manager.stats.total_downloads + 1,
                successful_downloads=self.stats_manager.stats.successful_downloads + 1,
                total_bytes=self.stats_manager.stats.total_bytes + task.total_size
            )
            
            if self.notification:
                await self.notification.notify(
                    f"✅ Download completed: {task.filename}\n"
                    f"Size: {self._format_size(task.total_size)}\n"
                    f"Time: {self._format_duration(task.end_time - task.start_time)}",
                    level="success"
                )
                
        except Exception as e:
            task.status = "failed"
            if self.notification:
                await self.notification.notify(
                    f"❌ Download failed: {task.filename}\n"
                    f"Error: {str(e)}",
                    level="error"
                )
            await self.stats_manager.update(
                total_downloads=self.stats_manager.stats.total_downloads + 1,
                failed_downloads=self.stats_manager.stats.failed_downloads + 1
            )
            
        finally:
            del self._active_downloads[task.file_id]

    def get_active_downloads(self) -> list:
        """Get list of current active downloads."""
        return [
            {
                'filename': task.filename,
                'progress': (task.bytes_downloaded / task.total_size) * 100 if task.total_size else 0,
                'status': task.status
            }
            for task in self._active_downloads.values()
        ]

    def get_queue_status(self) -> str:
        """Get formatted queue status message."""
        active = len(self._active_downloads)
        queued = self._download_queue.qsize()
        
        if active == 0 and queued == 0:
            return "No active or queued downloads"
            
        status = []
        if active > 0:
            status.append(f"Active downloads: {active}")
        if queued > 0:
            status.append(f"Queued downloads: {queued}")
            
        return "\n".join(status)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes into human readable size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into human readable duration."""
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        
        return " ".join(parts)

    @staticmethod
    def _get_safe_filename(filename: str) -> str:
        """Convert filename to safe version."""
        # Remove invalid characters
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        # Ensure it's not too long
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
        return filename