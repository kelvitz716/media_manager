"""Tests for the rate limiting components."""
import pytest
import asyncio
import time
from unittest import mock
from media_manager.common.rate_limiters import AsyncRateLimiter, ThreadedRateLimiter, SpeedLimiter

@pytest.mark.asyncio
async def test_async_rate_limiter():
    """Test async rate limiter."""
    limiter = AsyncRateLimiter(min_interval=0.1)
    key = "test"
    
    # First update should be allowed
    assert await limiter.can_update(key) is True
    
    # Immediate second update should be blocked
    assert await limiter.can_update(key) is False
    
    # Wait and try again
    await asyncio.sleep(0.2)
    assert await limiter.can_update(key) is True

@pytest.mark.asyncio
async def test_async_rate_limiter_multiple_keys():
    """Test async rate limiter with different keys."""
    limiter = AsyncRateLimiter(min_interval=0.1)
    
    # Different keys should be independent
    assert await limiter.can_update("key1") is True
    assert await limiter.can_update("key2") is True
    
    # Same keys should still be rate limited
    assert await limiter.can_update("key1") is False
    assert await limiter.can_update("key2") is False

@pytest.mark.asyncio
async def test_async_rate_limiter_wait():
    """Test wait_if_needed function."""
    limiter = AsyncRateLimiter(min_interval=0.1)
    key = "test"
    
    # First call should return immediately
    start = time.time()
    await limiter.wait_if_needed(key)
    assert time.time() - start < 0.05  # Allow some margin
    
    # Second call should wait
    start = time.time()
    await limiter.wait_if_needed(key)
    elapsed = time.time() - start
    assert 0.1 <= elapsed < 0.15  # Allow some margin

def test_threaded_rate_limiter():
    """Test threaded rate limiter."""
    limiter = ThreadedRateLimiter(min_interval=0.1)
    key = "test"
    
    # First call should return immediately
    start = time.time()
    limiter.wait_if_needed(key)
    assert time.time() - start < 0.05
    
    # Second call should wait
    start = time.time()
    limiter.wait_if_needed(key)
    elapsed = time.time() - start
    assert 0.1 <= elapsed < 0.15

def test_threaded_rate_limiter_multiple_keys():
    """Test threaded rate limiter with different keys."""
    limiter = ThreadedRateLimiter(min_interval=0.1)
    
    # Different keys should be independent
    start = time.time()
    limiter.wait_if_needed("key1")
    limiter.wait_if_needed("key2")
    assert time.time() - start < 0.05

@pytest.mark.asyncio
async def test_speed_limiter_no_limit():
    """Test speed limiter with no limit set."""
    limiter = SpeedLimiter()
    
    # Should return immediately with no limit
    start = time.time()
    await limiter.limit(1024 * 1024)  # 1MB
    assert time.time() - start < 0.05

@pytest.mark.asyncio
async def test_speed_limiter():
    """Test speed limiter with limit."""
    # Set 2 MB/s limit
    limiter = SpeedLimiter(max_speed_mbps=16)  # 16 Mbps = 2 MB/s
    chunk_size = 1024 * 1024  # 1MB
    
    # First chunk should go through immediately
    start = time.time()
    await limiter.limit(chunk_size)
    assert time.time() - start < 0.05
    
    # Second chunk should be delayed to maintain speed limit
    start = time.time()
    await limiter.limit(chunk_size)
    elapsed = time.time() - start
    assert 0.45 <= elapsed < 0.55  # Around 0.5s for 1MB at 2MB/s

@pytest.mark.asyncio
async def test_speed_limiter_small_chunks():
    """Test speed limiter with small chunks."""
    limiter = SpeedLimiter(max_speed_mbps=8)  # 8 Mbps = 1 MB/s
    chunk_size = 1024  # 1KB
    
    # Send 1024 chunks of 1KB (total 1MB)
    start = time.time()
    for _ in range(1024):
        await limiter.limit(chunk_size)
    elapsed = time.time() - start
    
    # Should take around 1 second to send 1MB at 1MB/s
    assert 0.9 <= elapsed < 1.1