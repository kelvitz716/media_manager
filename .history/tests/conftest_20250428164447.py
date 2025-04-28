"""Common test fixtures and configuration."""
import os
import asyncio
import pytest
import platform

# Configure event loop policy for Windows if needed
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def base_config():
    """Base configuration for testing."""
    return {
        "paths": {
            "telegram_download_dir": "downloads",
            "movies_dir": "media/movies",
            "tv_shows_dir": "media/tv_shows",
            "unmatched_dir": "media/unmatched"
        },
        "tmdb": {
            "api_key": "test_key"
        },
        "telegram": {
            "api_id": "test_id",
            "api_hash": "test_hash",
            "bot_token": "test_token",
            "enabled": True,
            "chat_id": "test_chat",
            "flood_sleep_threshold": 60
        },
        "logging": {
            "level": "DEBUG",
            "max_size_mb": 10,
            "backup_count": 5
        },
        "download": {
            "chunk_size": 1048576,
            "progress_update_interval": 5,
            "max_retries": 3,
            "retry_delay": 5,
            "max_concurrent_downloads": 3,
            "verify_downloads": True
        },
        "notification": {
            "enabled": True,
            "method": "telegram",
            "bot_token": "test_token",
            "chat_id": "test_chat"
        }
    }

@pytest.fixture(autouse=True)
def setup_test_env(base_config):
    """Setup test environment variables."""
    test_env = {
        "TELEGRAM_API_ID": base_config["telegram"]["api_id"],
        "TELEGRAM_API_HASH": base_config["telegram"]["api_hash"],
        "TELEGRAM_BOT_TOKEN": base_config["telegram"]["bot_token"],
        "TELEGRAM_CHAT_ID": base_config["telegram"]["chat_id"],
        "TMDB_API_KEY": base_config["tmdb"]["api_key"],
        "LOG_LEVEL": base_config["logging"]["level"]
    }
    
    # Store original env vars
    old_env = {}
    for key, value in test_env.items():
        old_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield
    
    # Restore original env vars
    for key, value in old_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

@pytest.fixture(scope="function")
async def mock_event_loop():
    """Create and provide a new event loop for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)