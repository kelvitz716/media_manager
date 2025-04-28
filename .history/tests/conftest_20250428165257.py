"""Test configuration and fixtures."""
import asyncio
import json
import os
import pytest
from unittest import mock

from media_manager.common.notification_service import NotificationService

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def config():
    """Create test configuration."""
    return {
        "paths": {
            "movies_dir": "media/movies",
            "tv_shows_dir": "media/tv_shows",
            "unmatched_dir": "media/unmatched"
        },
        "tmdb": {
            "api_key": "test_key"
        },
        "logging": {
            "level": "DEBUG",
            "filename": "media_watcher.log",
            "max_size_mb": 10,
            "backup_count": 3
        },
        "telegram": {
            "bot_token": "test_token",
            "chat_id": "test_chat_id"
        }
    }

@pytest.fixture
def mock_tmdb():
    """Create mock TMDB client."""
    return mock.AsyncMock()

@pytest.fixture
def mock_categorizer():
    """Create mock media categorizer."""
    return mock.AsyncMock()

@pytest.fixture
def notification_service():
    """Create notification service instance with mocked bot."""
    service = NotificationService(mock.Mock())
    service.bot = mock.AsyncMock()
    return service