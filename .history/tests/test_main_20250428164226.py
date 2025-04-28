"""Tests for main application functionality."""
import os
import signal
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from media_manager.main import MediaManager

@pytest.fixture
def config():
    """Test configuration."""
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
            "enabled": True
        },
        "notification": {
            "enabled": True,
            "method": "telegram",
            "bot_token": "test_token",
            "chat_id": "test_chat"
        }
    }

@pytest.fixture
async def manager(config):
    """Create manager instance with mocked components."""
    with patch("media_manager.main.ConfigManager") as mock_config:
        mock_config.return_value.config = config
        manager = MediaManager()
        yield manager
        await manager.shutdown()

@pytest.mark.asyncio
async def test_media_manager_initialization(manager):
    """Test manager initialization."""
    assert manager.stop_event is None
    assert manager.watcher_task is None
    assert manager.downloader_task is None

@pytest.mark.asyncio
async def test_media_manager_start(manager):
    """Test manager start."""
    await manager.start()
    assert manager.stop_event is not None
    assert manager.watcher_task is not None
    assert manager.downloader_task is not None
    assert not manager.stop_event.is_set()

@pytest.mark.asyncio
async def test_media_manager_shutdown(manager):
    """Test manager shutdown."""
    await manager.start()
    await manager.shutdown()
    assert manager.stop_event.is_set()
    assert manager.watcher_task is None
    assert manager.downloader_task is None

@pytest.mark.asyncio
async def test_media_manager_signal_handling(manager):
    """Test signal handling."""
    # Mock signal handler registration
    with patch("signal.signal") as mock_signal:
        await manager.start()
        mock_signal.assert_any_call(signal.SIGINT, manager._signal_handler)
        mock_signal.assert_any_call(signal.SIGTERM, manager._signal_handler)

    # Simulate signal handler call
    manager._signal_handler(signal.SIGTERM, None)
    assert manager.stop_event.is_set()

@pytest.mark.asyncio
async def test_main_entry_point():
    """Test main entry point."""
    # Mock manager and asyncio.run
    with patch("media_manager.main.MediaManager") as mock_manager_class, \
         patch("asyncio.run") as mock_run:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager
        
        from media_manager.main import main
        main()
        
        mock_run.assert_called_once()
        mock_manager.start.assert_called_once()

@pytest.mark.asyncio
async def test_main_error_handling():
    """Test error handling in main."""
    with patch("media_manager.main.MediaManager") as mock_manager_class, \
         patch("asyncio.run", side_effect=Exception("Test error")), \
         patch("sys.exit") as mock_exit:
        
        from media_manager.main import main
        main()
        
        mock_exit.assert_called_once_with(1)