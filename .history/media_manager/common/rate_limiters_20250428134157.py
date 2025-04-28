"""Rate limiting utilities for API calls and notifications."""
import asyncio
import threading
import time
from typing import Dict, Union

class AsyncRateLimiter:
    """Asynchronous rate limiter for API calls and notifications."""
    
    def __init__(self, min_interval: float = 2.0):
        """
        Initialize rate limiter.
        
        Args:
            min_interval: Minimum seconds between updates
        """
        self.last_update: Dict[Union[int, str], float] = {}
        self.min_interval = min_interval
        self.lock = asyncio.Lock()
        
    async def can_update(self, key: Union[int, str]) -> bool:
        """Check if an update is allowed."""
        async with self.lock:
            now = time.time()
            if key not in self.last_update:
                self.last_update[key] = now
                return True
            
            if now - self.last_update[key] >= self.min_interval:
                self.last_update[key] = now
                return True
            return False
            
    async def wait_if_needed(self, key: Union[int, str]) -> None:
        """Wait until an update is allowed."""
        async with self.lock:
            now = time.time()
            if key in self.last_update:
                time_since_last = now - self.last_update[key]
                if time_since_last < self.min_interval:
                    await asyncio.sleep(self.min_interval - time_since_last)
            
            self.last_update[key] = time.time()

class ThreadedRateLimiter:
    """Thread-safe rate limiter for synchronous code."""
    
    def __init__(self, min_interval: float = 2.0):
        """
        Initialize rate limiter.
        
        Args:
            min_interval: Minimum seconds between updates
        """
        self.min_interval = min_interval
        self.last_update = {}
        self._lock = threading.Lock()
    
    def wait_if_needed(self, key: str) -> None:
        """Wait if needed to respect rate limit."""
        now = time.time()
        with self._lock:
            if key in self.last_update:
                elapsed = now - self.last_update[key]
                if elapsed < self.min_interval:
                    time.sleep(self.min_interval - elapsed)
            self.last_update[key] = time.time()

class SpeedLimiter:
    """Limits download/upload speed."""
    
    def __init__(self, max_speed_mbps: float = None):
        """
        Initialize speed limiter.
        
        Args:
            max_speed_mbps: Maximum speed in Mbps
        """
        self.max_speed_mbps = max_speed_mbps
        self._last_check = time.time()
        self._bytes_since_check = 0
        self._lock = asyncio.Lock()
        self._start_time = time.time()

    async def limit(self, chunk_size: int) -> None:
        """Limit speed by adding delays if needed."""
        if not self.max_speed_mbps:
            return

        async with self._lock:
            current_time = time.time()
            self._bytes_since_check += chunk_size
            
            # Calculate target time based on speed limit
            target_time = self._start_time + (self._bytes_since_check * 8) / (self.max_speed_mbps * 1024 * 1024)
            
            if current_time < target_time:
                await asyncio.sleep(target_time - current_time)