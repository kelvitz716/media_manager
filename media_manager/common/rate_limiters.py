"""Rate limiting components."""
import time
import asyncio
import threading
from typing import Dict, Any, Optional, Union
from collections import defaultdict

class AsyncRateLimiter:
    """Rate limiter for async operations."""
    
    def __init__(self, min_interval: float = 1.0):
        """Initialize rate limiter.
        
        Args:
            min_interval: Minimum interval between updates in seconds
        """
        self.min_interval = min_interval
        self._last_update: Dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()
        self._context_depth = 0
    
    async def __aenter__(self):
        """Enter async context."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        return None
    
    async def can_update(self, key: str) -> bool:
        """Check if operation can proceed."""
        now = time.time()
        if now - self._last_update[key] >= self.min_interval:
            self._last_update[key] = now
            return True
        return False
    
    async def wait_if_needed(self, key: str) -> None:
        """Wait until operation can proceed."""
        now = time.time()
        elapsed = now - self._last_update[key]
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self._last_update[key] = time.time()

class ThreadedRateLimiter:
    """Rate limiter for threaded operations."""
    
    def __init__(self, min_interval: float = 1.0):
        """Initialize rate limiter.
        
        Args:
            min_interval: Minimum interval between updates in seconds
        """
        self.min_interval = min_interval
        self._last_update: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def can_update(self, key: str) -> bool:
        """Check if operation can proceed."""
        with self._lock:
            now = time.time()
            if now - self._last_update[key] >= self.min_interval:
                self._last_update[key] = now
                return True
            return False
    
    def wait_if_needed(self, key: str) -> None:
        """Wait until operation can proceed."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update[key]
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_update[key] = time.time()

class SpeedLimiter:
    """Limits data transfer speed."""
    
    def __init__(self, max_speed_mbps: Optional[float] = None):
        """Initialize speed limiter.
        
        Args:
            max_speed_mbps: Maximum speed in megabits per second
        """
        self.max_speed_mbps = max_speed_mbps
        self._bytes_sent = 0
        self._last_reset = time.time()
        self._lock = asyncio.Lock()
    
    def _reset_if_needed(self) -> None:
        """Reset counters if too much time has passed."""
        now = time.time()
        if now - self._last_reset > 1.0:  # Reset every second
            self._bytes_sent = 0
            self._last_reset = now
    
    def _get_delay(self, chunk_size: int) -> float:
        """Calculate delay needed to maintain speed limit."""
        if not self.max_speed_mbps:
            return 0.0
            
        # Convert Mbps to bytes/sec (1 Mbps = 1,000,000 bits/sec = 125,000 bytes/sec)
        max_bytes_per_sec = self.max_speed_mbps * 125000
        self._reset_if_needed()
        
        # Don't delay if this is the first chunk after reset
        if self._bytes_sent == 0:
            return 0.0
        
        elapsed = time.time() - self._last_reset
        target_time = self._bytes_sent / max_bytes_per_sec
        
        # Calculate the delay needed to maintain the target speed
        delay = max(0.0, target_time - elapsed)
        return delay
    
    async def limit(self, chunk_size: int) -> None:
        """Limit speed for a chunk of data.
        
        Args:
            chunk_size: Size of data chunk in bytes
        """
        if not self.max_speed_mbps:
            return
            
        async with self._lock:
            delay = self._get_delay(chunk_size)
            if delay > 0:
                await asyncio.sleep(delay)
            self._bytes_sent += chunk_size

class StatsManager:
    """Manages statistics and metrics."""
    
    def __init__(self):
        """Initialize stats manager."""
        self._stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: defaultdict(float))
        self._start_time = time.time()
        self._lock = threading.Lock()
    
    def increment(self, category: str, metric: str, value: float = 1.0) -> None:
        """Increment a metric value.
        
        Args:
            category: Category of the metric (e.g., 'downloads', 'api_calls')
            metric: Name of the metric to increment
            value: Value to add (default: 1.0)
        """
        with self._lock:
            self._stats[category][metric] += value
    
    def set(self, category: str, metric: str, value: Any) -> None:
        """Set a metric value.
        
        Args:
            category: Category of the metric
            metric: Name of the metric
            value: Value to set
        """
        with self._lock:
            self._stats[category][metric] = value
    
    def get(self, category: str, metric: str) -> Any:
        """Get a metric value.
        
        Args:
            category: Category of the metric
            metric: Name of the metric
            
        Returns:
            Current value of the metric
        """
        with self._lock:
            return self._stats[category][metric]
    
    def get_category(self, category: str) -> Dict[str, Any]:
        """Get all metrics for a category.
        
        Args:
            category: Category to get metrics for
            
        Returns:
            Dictionary of metric names and values
        """
        with self._lock:
            return dict(self._stats[category])
    
    def get_stats(self) -> str:
        """Get formatted statistics summary.
        
        Returns:
            Formatted statistics string
        """
        with self._lock:
            total_files = int(self._stats['downloads']['total'])
            successful = int(self._stats['downloads']['successful'])
            failed = int(self._stats['downloads']['failed'])
            total_bytes = self._stats['downloads']['total_bytes']
            avg_speed = self._stats['downloads']['avg_speed']
            avg_time = self._stats['downloads']['avg_time']
            peak_concurrent = int(self._stats['downloads']['peak_concurrent'])
            active = int(self._stats['downloads']['active'])
            queued = int(self._stats['downloads']['queued'])
            
            uptime = time.time() - self._start_time
            success_rate = (successful / total_files * 100) if total_files > 0 else 0
            
            return (
                "📊 DOWNLOAD STATISTICS\n\n"
                f"📆 Bot uptime: {int(uptime)}s\n"
                f"📥 Files handled: {total_files}\n\n"
                f"DOWNLOADS:\n"
                f"✅ Successful: {successful} ({success_rate:.1f}%)\n"
                f"❌ Failed: {failed} ({100-success_rate:.1f}%)\n"
                f"💾 Total data: {total_bytes / (1024**3):.1f} GB\n\n"
                f"PERFORMANCE:\n"
                f"⚡ Average speed: {avg_speed:.1f} MB/s\n"
                f"⏱️ Avg time per file: {int(avg_time/60)}m {int(avg_time%60)}s\n"
                f"📊 Peak concurrent downloads: {peak_concurrent}/3\n\n"
                f"⏳ Current status: {active} active, {queued} queued"
            )