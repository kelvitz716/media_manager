"""Rate limiting components."""
import time
import asyncio
from typing import Dict, Any, Optional
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
    
    def can_update(self, key: str) -> bool:
        """Check if operation can proceed."""
        now = time.time()
        if now - self._last_update[key] >= self.min_interval:
            self._last_update[key] = now
            return True
        return False
    
    def wait_if_needed(self, key: str) -> None:
        """Wait until operation can proceed."""
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
        self._start_time = time.time()
        self._last_reset = self._start_time
    
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
            
        max_bytes_per_sec = self.max_speed_mbps * 125000  # Convert Mbps to bytes/sec
        self._reset_if_needed()
        
        elapsed = time.time() - self._last_reset
        allowed_bytes = max_bytes_per_sec * elapsed
        
        if self._bytes_sent + chunk_size > allowed_bytes:
            # Calculate delay needed
            needed_time = (self._bytes_sent + chunk_size) / max_bytes_per_sec
            return max(0.0, needed_time - elapsed)
        return 0.0
    
    async def limit(self, chunk_size: int) -> None:
        """Limit speed for a chunk of data.
        
        Args:
            chunk_size: Size of data chunk in bytes
        """
        if not self.max_speed_mbps:
            return
            
        delay = self._get_delay(chunk_size)
        if delay > 0:
            await asyncio.sleep(delay)
        
        self._bytes_sent += chunk_size