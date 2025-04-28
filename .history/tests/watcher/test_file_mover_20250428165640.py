"""Tests for media watcher module."""
import os
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

from media_manager.watcher.file_mover import MediaWatcher

@pytest.fixture
def config():
    """Create test configuration."""
    return {
        "paths": {
            "movies_dir": "media/movies",
            "tv_shows_dir": "media/tv_shows",
            "unmatched_dir": "media/unmatched",
            "watch_dir": "media/watch"
        }
    }

@pytest.fixture
def mock_categorizer():
    """Create mock media categorizer."""
    return AsyncMock()

@pytest.fixture
def mock_notifier():
    """Create mock notification service."""
    notifier = AsyncMock()
    notifier.notify = AsyncMock()
    return notifier

@pytest.fixture
def media_watcher(config, mock_categorizer, mock_notifier):
    """Create media watcher instance."""
    return MediaWatcher(config, mock_categorizer, mock_notifier)

@pytest.mark.asyncio
async def test_media_file_handler_initialization(media_watcher):
    """Test media file handler initialization."""
    assert media_watcher.categorizer is not None
    assert media_watcher.config is not None

@pytest.mark.asyncio
async def test_media_file_handler_new_file(media_watcher, mock_categorizer):
    """Test handling new media file."""
    test_file = "test_movie.mkv"
    mock_categorizer.process_file.return_value = True
    
    await media_watcher._handle_media_file(test_file)
    mock_categorizer.process_file.assert_called_once_with(test_file)

@pytest.mark.asyncio
async def test_media_file_handler_failed_processing(media_watcher, mock_categorizer, mock_notifier):
    """Test handling failed media file processing."""
    test_file = "test_movie.mkv"
    mock_categorizer.process_file.side_effect = Exception("Processing error")
    
    await media_watcher._handle_media_file(test_file)
    mock_notifier.notify.assert_called_once()

@pytest.mark.asyncio
async def test_media_file_handler_duplicate_processing(media_watcher, mock_categorizer):
    """Test handling duplicate file processing."""
    test_file = "test_movie.mkv"
    media_watcher._processing_files.add(test_file)
    
    await media_watcher._handle_media_file(test_file)
    mock_categorizer.process_file.assert_not_called()

@pytest.mark.asyncio
async def test_media_watcher_initialization(config, mock_categorizer, mock_notifier):
    """Test media watcher initialization."""
    watcher = MediaWatcher(config, mock_categorizer, mock_notifier)
    assert watcher.watch_dir == Path(config["paths"]["watch_dir"])

@pytest.mark.asyncio
async def test_media_watcher_start_stop(media_watcher):
    """Test starting and stopping media watcher."""
    # Mock the watch directory creation
    with patch("pathlib.Path.mkdir") as mock_mkdir:
        # Start the watcher
        await media_watcher.start()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        
        # Stop the watcher
        await media_watcher.stop()
        assert not media_watcher._running

@pytest.mark.asyncio
async def test_media_watcher_process_existing(media_watcher, mock_categorizer):
    """Test processing existing files."""
    test_files = ["test1.mkv", "test2.mkv"]
    
    # Mock the watch directory listing
    with patch("os.listdir", return_value=test_files):
        await media_watcher._process_existing_files()
        assert mock_categorizer.process_file.call_count == len(test_files)