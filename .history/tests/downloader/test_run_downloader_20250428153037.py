"""Tests for the downloader runner script."""
import os
import signal
import asyncio
import pytest
from unittest import mock
from media_manager.downloader.run_downloader import main
from media_manager.common.config_manager import ConfigManager
from media_manager.common.notification_service import NotificationService
from media_manager.downloader.bot import TelegramDownloader

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
            "telegram_download_dir": "/tmp/test_downloads"
        }
    }

@pytest.fixture
def mock_config_manager(mock_config):
    """Mock ConfigManager."""
    with mock.patch('media_manager.downloader.run_downloader.ConfigManager') as mock_cm:
        instance = mock_cm.return_value
        instance.config = mock_config
        yield instance

@pytest.mark.asyncio
async def test_main_successful_startup(mock_config_manager):
    """Test successful startup of the downloader."""
    with mock.patch('media_manager.downloader.run_downloader.setup_logging') as mock_logging, \
         mock.patch('media_manager.downloader.run_downloader.NotificationService') as mock_notif, \
         mock.patch('media_manager.downloader.run_downloader.TelegramDownloader') as mock_downloader, \
         mock.patch('os.makedirs') as mock_makedirs:
        
        # Configure mocks
        mock_downloader_instance = mock_downloader.return_value
        mock_downloader_instance.start = mock.AsyncMock()
        mock_downloader_instance.stop = mock.AsyncMock()
        
        # Run main
        await main()
        
        # Verify setup sequence
        mock_config_manager.assert_called_once()
        mock_logging.assert_called_once()
        mock_notif.assert_called_once()
        mock_downloader.assert_called_once()
        mock_makedirs.assert_called_once_with('/tmp/test_downloads', exist_ok=True)
        mock_downloader_instance.start.assert_called_once()
        mock_downloader_instance.stop.assert_not_called()

@pytest.mark.asyncio
async def test_main_startup_error(mock_config_manager):
    """Test handling of startup errors."""
    with mock.patch('media_manager.downloader.run_downloader.setup_logging') as mock_logging, \
         mock.patch('media_manager.downloader.run_downloader.NotificationService') as mock_notif, \
         mock.patch('media_manager.downloader.run_downloader.TelegramDownloader') as mock_downloader:
        
        # Configure mocks
        mock_downloader_instance = mock_downloader.return_value
        mock_downloader_instance.start = mock.AsyncMock(side_effect=Exception("Startup failed"))
        mock_downloader_instance.stop = mock.AsyncMock()
        
        # Run main
        await main()
        
        # Verify error handling
        mock_downloader_instance.start.assert_called_once()
        mock_downloader_instance.stop.assert_called_once()

@pytest.mark.asyncio
async def test_main_signal_handling(mock_config_manager):
    """Test signal handler registration and handling."""
    with mock.patch('media_manager.downloader.run_downloader.setup_logging'), \
         mock.patch('media_manager.downloader.run_downloader.NotificationService'), \
         mock.patch('media_manager.downloader.run_downloader.TelegramDownloader') as mock_downloader, \
         mock.patch('signal.signal') as mock_signal:
        
        # Configure mocks
        mock_downloader_instance = mock_downloader.return_value
        mock_downloader_instance.start = mock.AsyncMock()
        mock_downloader_instance.stop = mock.AsyncMock()
        
        # Run main
        await main()
        
        # Verify signal handlers were registered
        assert mock_signal.call_count == 2  # SIGTERM and SIGINT
        signal_calls = [call[0][0] for call in mock_signal.call_args_list]
        assert signal.SIGTERM in signal_calls
        assert signal.SIGINT in signal_calls

@pytest.mark.asyncio
async def test_main_directory_creation_error(mock_config_manager):
    """Test handling of directory creation errors."""
    with mock.patch('media_manager.downloader.run_downloader.setup_logging'), \
         mock.patch('media_manager.downloader.run_downloader.NotificationService'), \
         mock.patch('media_manager.downloader.run_downloader.TelegramDownloader') as mock_downloader, \
         mock.patch('os.makedirs', side_effect=PermissionError("Access denied")):
        
        mock_downloader_instance = mock_downloader.return_value
        mock_downloader_instance.stop = mock.AsyncMock()
        
        # Run main
        await main()
        
        # Verify downloader was stopped
        mock_downloader_instance.stop.assert_called_once()

@pytest.mark.asyncio
async def test_config_loading_error(mock_config_manager):
    """Test handling of configuration loading errors."""
    mock_config_manager.side_effect = Exception("Config load failed")
    
    with mock.patch('media_manager.downloader.run_downloader.setup_logging'), \
         mock.patch('media_manager.downloader.run_downloader.NotificationService'), \
         mock.patch('media_manager.downloader.run_downloader.TelegramDownloader') as mock_downloader:
        
        # Run main
        await main()
        
        # Verify downloader was not started
        mock_downloader.assert_not_called()