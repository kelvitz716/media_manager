"""Tests for rate limiting utilities."""
import asyncio
import time
from unittest import TestCase, IsolatedAsyncioTestCase
from media_manager.common.rate_limiters import AsyncRateLimiter, ThreadedRateLimiter, SpeedLimiter

class TestAsyncRateLimiter(IsolatedAsyncioTestCase):
    """Test cases for AsyncRateLimiter."""
    
    async def test_initial_update_allowed(self):
        """Test first update is always allowed."""
        limiter = AsyncRateLimiter(min_interval=1.0)
        allowed = await limiter.can_update("test_key")
        self.assertTrue(allowed)
        
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        limiter = AsyncRateLimiter(min_interval=0.1)
        
        # First update should be allowed
        await limiter.wait_if_needed("test_key")
        first_time = time.time()
        
        # Second immediate update should be delayed
        await limiter.wait_if_needed("test_key")
        second_time = time.time()
        
        # Check that appropriate delay was applied
        self.assertGreaterEqual(second_time - first_time, 0.1)
        
    async def test_multiple_keys(self):
        """Test rate limiting with different keys."""
        limiter = AsyncRateLimiter(min_interval=0.1)
        
        # Updates for different keys should not be delayed
        await limiter.wait_if_needed("key1")
        first_time = time.time()
        
        await limiter.wait_if_needed("key2")
        second_time = time.time()
        
        # Should be almost immediate
        self.assertLess(second_time - first_time, 0.1)

class TestThreadedRateLimiter(TestCase):
    """Test cases for ThreadedRateLimiter."""
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        limiter = ThreadedRateLimiter(min_interval=0.1)
        
        # First update
        limiter.wait_if_needed("test_key")
        first_time = time.time()
        
        # Second update
        limiter.wait_if_needed("test_key")
        second_time = time.time()
        
        # Check delay
        self.assertGreaterEqual(second_time - first_time, 0.1)

class TestSpeedLimiter(IsolatedAsyncioTestCase):
    """Test cases for SpeedLimiter."""
    
    async def test_no_limit(self):
        """Test when no speed limit is set."""
        limiter = SpeedLimiter(max_speed_mbps=None)
        start_time = time.time()
        
        # Should return immediately
        await limiter.limit(1024 * 1024)  # 1MB
        end_time = time.time()
        
        self.assertLess(end_time - start_time, 0.1)
        
    async def test_speed_limiting(self):
        """Test speed limiting functionality."""
        # Set 1 Mbps limit
        limiter = SpeedLimiter(max_speed_mbps=1.0)
        start_time = time.time()
        
        # Try to transfer 1MB
        await limiter.limit(1024 * 1024)
        end_time = time.time()
        
        # Should take at least 8 seconds (8Mb at 1Mbps)
        self.assertGreaterEqual(end_time - start_time, 8.0)
        
    async def test_multiple_chunks(self):
        """Test speed limiting with multiple chunks."""
        limiter = SpeedLimiter(max_speed_mbps=2.0)
        chunks = [1024 * 64] * 4  # 4 chunks of 64KB
        
        start_time = time.time()
        for chunk_size in chunks:
            await limiter.limit(chunk_size)
        end_time = time.time()
        
        # Total data: 256KB = 2Mb
        # At 2Mbps should take at least 1 second
        self.assertGreaterEqual(end_time - start_time, 1.0)