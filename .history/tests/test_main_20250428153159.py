"""Tests for the main Media Manager coordinator."""
import os
import signal
import asyncio
import pytest
from unittest import mock
from media_manager.main import MediaManager, main

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "logging": {
            "level": "INFO",
            "max_size_mb": 10,
            "backup_count": 5
        },
        "notification": {
            "enabled": True
        },
        "paths": {
            "telegram_download_dir": "/tmp/downloads",
            "movies_dir": "/tmp/movies",
            "tv_shows_dir": "/tmp/tv_shows",
            "unmatched_dir": "/tmp/unmatched"
        }
    }

@pytest.fixture
def mock_config_manager(mock_config):
    """Mock ConfigManager."""
    with mock.patch('media_manager.main.ConfigManager') as mock_cm:
        instance = mock_cm.return_value
        instance.config = mock_config
        yield instance

@pytest.mark.asyncio
async def test_media_manager_initialization(mock_config_manager):
    """Test successful initialization of MediaManager."""
    with mock.patch('media_manager.main.setup_logging') as mock_logging, \
         mock.patch('media_manager.main.NotificationService') as mock_notif, \
         mock.patch('media_manager.main.TelegramDownloader') as mock_downloader, \
         mock.patch('media_manager.main.MediaWatcher') as mock_watcher:
        
        # Create manager instance
        manager = MediaManager()
        
        # Verify initialization sequence
        mock_config_manager.assert_called_once()
        mock_logging.assert_called_once()
        mock_notif.assert_called_once()
        mock_downloader.assert_called_once()
        mock_watcher.assert_called_once()
        
        # Verify signal handlers were set up
        assert signal.getsignal(signal.SIGTERM) == manager._handle_shutdown
        assert signal.getsignal(signal.SIGINT) == manager._handle_shutdown

@pytest.mark.asyncio
async def test_media_manager_start(mock_config_manager):
    """Test starting the Media Manager and its components."""
    with mock.patch('media_manager.main.setup_logging'), \
         mock.patch('media_manager.main.NotificationService'), \
         mock.patch('media_manager.main.TelegramDownloader') as mock_downloader, \
         mock.patch('media_manager.main.MediaWatcher') as mock_watcher, \
         mock.patch('os.makedirs') as mock_makedirs:
        
        # Configure mocks
        mock_downloader_instance = mock_downloader.return_value
        mock_downloader_instance.start = mock.AsyncMock()
        mock_watcher_instance = mock_watcher.return_value
        mock_watcher_instance.start = mock.MagicMock()
        
        # Create and start manager
        manager = MediaManager()
        await manager.start()
        
        # Verify directories were created
        assert mock_makedirs.call_count == len(mock_config_manager().config["paths"])
        mock_makedirs.assert_has_calls([
            mock.call('/tmp/downloads', exist_ok=True),
            mock.call('/tmp/movies', exist_ok=True),
            mock.call('/tmp/tv_shows', exist_ok=True),
            mock.call('/tmp/unmatched', exist_ok=True)
        ], any_order=True)
        
        # Verify components were started
        mock_watcher_instance.start.assert_called_once()
        mock_downloader_instance.start.assert_called_once()

@pytest.mark.asyncio
async def test_media_manager_shutdown(mock_config_manager):
    """Test graceful shutdown of Media Manager."""
    with mock.patch('media_manager.main.setup_logging'), \
         mock.patch('media_manager.main.NotificationService'), \
         mock.patch('media_manager.main.TelegramDownloader') as mock_downloader, \
         mock.patch('media_manager.main.MediaWatcher') as mock_watcher:
        
        # Configure mocks
        mock_downloader_instance = mock_downloader.return_value
        mock_downloader_instance.stop = mock.AsyncMock()
        mock_watcher_instance = mock_watcher.return_value
        mock_watcher_instance.stop = mock.MagicMock()
        
        # Create manager and simulate shutdown
        manager = MediaManager()
        await manager._shutdown()
        
        # Verify components were stopped
        mock_downloader_instance.stop.assert_called_once()
        mock_watcher_instance.stop.assert_called_once()

@pytest.mark.asyncio
async def test_media_manager_signal_handling(mock_config_manager):
    """Test signal handling during shutdown."""
    with mock.patch('media_manager.main.setup_logging'), \
         mock.patch('media_manager.main.NotificationService'), \
         mock.patch('media_manager.main.TelegramDownloader') as mock_downloader, \
         mock.patch('media_manager.main.MediaWatcher') as mock_watcher, \
         mock.patch('asyncio.create_task') as mock_create_task:
        
        # Configure component mocks
        mock_downloader_instance = mock_downloader.return_value
        mock_downloader_instance.stop = mock.AsyncMock()
        mock_watcher_instance = mock_watcher.return_value
        mock_watcher_instance.stop = mock.MagicMock()
        
        # Create manager
        manager = MediaManager()
        
        # Simulate signal
        manager._handle_shutdown(signal.SIGTERM, None)
        
        # Verify shutdown was initiated
        mock_create_task.assert_called_once()

@pytest.mark.asyncio
async def test_main_entry_point():
    """Test the main entry point function."""
    with mock.patch('media_manager.main.MediaManager') as mock_manager_class, \
         mock.patch('asyncio.get_event_loop') as mock_get_loop:
        
        # Configure mocks
        mock_manager = mock_manager_class.return_value
        mock_manager.start = mock.AsyncMock()
        mock_loop = mock_get_loop.return_value
        mock_loop.run_until_complete = mock.MagicMock()
        mock_loop.run_forever = mock.MagicMock()
        mock_loop.close = mock.MagicMock()
        
        # Run main
        await main()
        
        # Verify execution flow
        mock_manager_class.assert_called_once()
        mock_manager.start.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()
        mock_loop.run_forever.assert_called_once()
        mock_loop.close.assert_called_once()

@pytest.mark.asyncio
async def test_main_error_handling():
    """Test error handling in main entry point."""
    with mock.patch('media_manager.main.MediaManager') as mock_manager_class, \
         mock.patch('asyncio.get_event_loop') as mock_get_loop, \
         mock.patch('logging.error') as mock_log_error:
        
        # Configure mocks to raise an error
        mock_manager = mock_manager_class.return_value
        mock_manager.start = mock.AsyncMock(side_effect=Exception("Test error"))
        mock_loop = mock_get_loop.return_value
        mock_loop.run_until_complete = mock.MagicMock(side_effect=Exception("Test error"))
        mock_loop.close = mock.MagicMock()
        
        # Run main
        await main()
        
        # Verify error was logged and loop was closed
        mock_log_error.assert_called_once()
        mock_loop.close.assert_called_once()