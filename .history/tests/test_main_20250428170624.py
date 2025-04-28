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
        "logging": {
            "level": "DEBUG",
            "max_size_mb": 10,
            "backup_count": 5,
            "log_dir": "logs"
        },
        "notification": {
            "enabled": True,
            "method": "telegram",
            "bot_token": "test_token",
            "chat_id": "test_chat"
        }
    }

@pytest.mark.asyncio
async def test_media_manager_initialization(config):
    """Test media manager initialization."""
    with patch("media_manager.main.ConfigManager") as mock_config, \
         patch("media_manager.main.setup_logging") as mock_logger, \
         patch("media_manager.main.NotificationService") as mock_notification, \
         patch("media_manager.main.MediaCategorizer") as mock_categorizer, \
         patch("media_manager.main.MediaWatcher") as mock_watcher:
        
        mock_config.return_value.config = config
        manager = MediaManager()
        await manager.initialize()
        
        mock_logger.assert_called_once()
        mock_notification.assert_called_once()
        mock_categorizer.assert_called_once()
        mock_watcher.assert_called_once()

@pytest.mark.asyncio
async def test_media_manager_start(config):
    """Test media manager start."""
    with patch("media_manager.main.ConfigManager") as mock_config, \
         patch("media_manager.main.setup_logging"), \
         patch("media_manager.main.NotificationService"), \
         patch("media_manager.main.MediaCategorizer"), \
         patch("media_manager.main.MediaWatcher") as mock_watcher:
        
        mock_config.return_value.config = config
        mock_instance = mock_watcher.return_value
        mock_instance.start = AsyncMock()
        
        manager = MediaManager()
        await manager.initialize()
        await manager.start()
        
        mock_instance.start.assert_called_once()

@pytest.mark.asyncio
async def test_media_manager_shutdown(config):
    """Test media manager shutdown."""
    with patch("media_manager.main.ConfigManager") as mock_config, \
         patch("media_manager.main.setup_logging"), \
         patch("media_manager.main.NotificationService"), \
         patch("media_manager.main.MediaCategorizer"), \
         patch("media_manager.main.MediaWatcher") as mock_watcher:
        
        mock_config.return_value.config = config
        mock_instance = mock_watcher.return_value
        mock_instance.stop = AsyncMock()
        
        manager = MediaManager()
        await manager.initialize()
        await manager.shutdown()
        
        mock_instance.stop.assert_called_once()

@pytest.mark.asyncio
async def test_media_manager_signal_handling(config):
    """Test signal handling."""
    with patch("media_manager.main.ConfigManager") as mock_config, \
         patch("media_manager.main.setup_logging"), \
         patch("media_manager.main.NotificationService"), \
         patch("media_manager.main.MediaCategorizer"), \
         patch("media_manager.main.MediaWatcher"):
        
        mock_config.return_value.config = config
        manager = MediaManager()
        await manager.initialize()
        
        # Simulate signal handling
        with patch.object(manager, 'shutdown', new_callable=AsyncMock) as mock_shutdown:
            manager._signal_handler(signal.SIGINT, None)
            await asyncio.sleep(0.1)  # Allow signal handler to process
            mock_shutdown.assert_called_once()

@pytest.mark.asyncio
async def test_main_entry_point():
    """Test main entry point."""
    with patch("media_manager.main.MediaManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager
        
        # Mock the async context manager methods
        mock_manager.__aenter__.return_value = mock_manager
        
        from media_manager.main import main
        await main()
        
        mock_manager.initialize.assert_called_once()
        mock_manager.start.assert_called_once()

@pytest.mark.asyncio
async def test_main_error_handling():
    """Test error handling in main."""
    with patch("media_manager.main.MediaManager") as mock_manager_class, \
         patch("media_manager.main.logger") as mock_logger:
        
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.initialize.side_effect = Exception("Test error")
        
        from media_manager.main import main
        await main()
        
        mock_logger.error.assert_called_once()