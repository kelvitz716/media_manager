"""Tests for downloader runner."""
import os
import signal
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from media_manager.downloader.run_downloader import TelegramDownloader, main

@pytest.fixture
def config():
    """Test configuration."""
    return {
        "paths": {
            "telegram_download_dir": "downloads"
        },
        "telegram": {
            "api_id": "test_id",
            "api_hash": "test_hash",
            "bot_token": "test_token",
            "enabled": True,
            "chat_id": "test_chat"
        }
    }

@pytest.fixture
async def downloader(config):
    """Create downloader instance."""
    with patch("media_manager.downloader.run_downloader.ConfigManager") as mock_config:
        mock_config.return_value.config = config
        downloader = TelegramDownloader()
        yield downloader
        await downloader.stop()

@pytest.mark.asyncio
async def test_main_successful_startup():
    """Test successful main startup."""
    mock_config = {
        "telegram": {"enabled": True},
        "paths": {"telegram_download_dir": "downloads"}
    }
    
    with patch("media_manager.downloader.run_downloader.ConfigManager") as mock_config_class, \
         patch("media_manager.downloader.run_downloader.TelegramDownloader") as mock_downloader_class:
            
        mock_config_class.return_value.config = mock_config
        mock_downloader = AsyncMock()
        mock_downloader_class.return_value = mock_downloader
        
        # Mock os.makedirs to avoid actual directory creation
        with patch("os.makedirs"):
            await main()
            
        mock_downloader.start.assert_called_once()
        mock_downloader.stop.assert_called_once()

@pytest.mark.asyncio
async def test_main_startup_error():
    """Test main startup with configuration error."""
    with patch("media_manager.downloader.run_downloader.ConfigManager",
              side_effect=Exception("Config error")), \
         patch("sys.exit") as mock_exit:
        await main()
        mock_exit.assert_called_once_with(1)

@pytest.mark.asyncio
async def test_main_signal_handling():
    """Test signal handling in main."""
    mock_config = {
        "telegram": {"enabled": True},
        "paths": {"telegram_download_dir": "downloads"}
    }
    
    with patch("media_manager.downloader.run_downloader.ConfigManager") as mock_config_class, \
         patch("media_manager.downloader.run_downloader.TelegramDownloader") as mock_downloader_class, \
         patch("signal.signal") as mock_signal:
            
        mock_config_class.return_value.config = mock_config
        mock_downloader = AsyncMock()
        mock_downloader_class.return_value = mock_downloader
        
        # Start main in background
        task = asyncio.create_task(main())
        await asyncio.sleep(0.1)  # Give it time to start
        
        # Simulate signal
        for handler in mock_signal.call_args_list:
            if handler[0][0] == signal.SIGTERM:
                handler[0][1](signal.SIGTERM, None)
                break
        
        await task
        mock_downloader.stop.assert_called_once()

@pytest.mark.asyncio
async def test_main_directory_creation_error():
    """Test main with directory creation error."""
    mock_config = {
        "telegram": {"enabled": True},
        "paths": {"telegram_download_dir": "/nonexistent/path"}
    }
    
    with patch("media_manager.downloader.run_downloader.ConfigManager") as mock_config_class, \
         patch("os.makedirs", side_effect=PermissionError), \
         patch("sys.exit") as mock_exit:
            
        mock_config_class.return_value.config = mock_config
        await main()
        mock_exit.assert_called_once_with(1)

@pytest.mark.asyncio
async def test_config_loading_error():
    """Test configuration loading error."""
    with patch("media_manager.downloader.run_downloader.ConfigManager",
              side_effect=Exception("Config error")), \
         patch("sys.exit") as mock_exit:
        await main()
        mock_exit.assert_called_with(1)