"""Download task class for managing download state and progress."""
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import datetime

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
            text = [f"📥 Downloading: {self.filename}"]
            
            if self.total_size:
                text.append(f"Progress: {self.progress_percentage:.1f}%")
                text.append(
                    f"Size: {self.bytes_downloaded/(1024*1024):.1f}/"
                    f"{self.total_size/(1024*1024):.1f} MB"
                )
                
            if self.speed > 0:
                text.append(f"Speed: {self.speed/1024/1024:.1f} MB/s")
                
            if self.eta:
                text.append(f"ETA: {datetime.timedelta(seconds=int(self.eta))}")
                
            return "\n".join(text)
            
        if self.status == "completed":
            elapsed = time.time() - self.start_time
            return (
                f"✅ Download Complete: {self.filename}\n"
                f"Time taken: {datetime.timedelta(seconds=int(elapsed))}\n\n"
                f"Starting media categorization..."
            )
            
        if self.status == "error":
            return f"❌ Error downloading {self.filename}"
            
        return f"Status: {self.status}"
        
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