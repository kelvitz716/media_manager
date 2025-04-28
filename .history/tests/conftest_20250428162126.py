"""Common test fixtures and configuration."""
import os
import asyncio
import pytest

# Configure asyncio to use event loop policy that works with pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    test_env = {
        "TELEGRAM_API_ID": "test_api_id",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_BOT_TOKEN": "test_bot_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
        "TMDB_API_KEY": "test_tmdb_key"
    }
    
    # Store original env vars
    old_env = {}
    for key in test_env:
        old_env[key] = os.environ.get(key)
        os.environ[key] = test_env[key]
    
    yield
    
    # Restore original env vars
    for key, value in old_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value