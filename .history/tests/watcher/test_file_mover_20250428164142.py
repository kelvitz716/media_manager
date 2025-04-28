"""Tests for file mover functionality."""
import os
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from media_manager.watcher.file_mover import MediaFileHandler, MediaWatcher
from media_manager.watcher.categorizer import MediaCategorizer

@pytest.fixture
def config():
    """Test configuration."""
    return {
        "paths": {
            "movies_dir": "media/movies",
            "tv_shows_dir": "media/tv_shows",
            "unmatched_dir": "media/unmatched"
        },
        "tmdb": {
            "api_key": "test_key"
        }
    }

@pytest.fixture
def mock_categorizer():
    """Mock categorizer."""
    mock = AsyncMock(spec=MediaCategorizer)
    mock.process_file.return_value = MagicMock(
        success=True,
        media_type="movie",
        destination="media/movies/Test Movie (2024)/Test.Movie.2024.mp4"
    )
    return mock

@pytest.fixture
def file_handler(config, mock_categorizer):
    """Create file handler instance."""
    with patch("media_manager.watcher.file_mover.MediaCategorizer", return_value=mock_categorizer):
        return MediaFileHandler(config)

@pytest.fixture
def watcher(config, mock_categorizer):
    """Create media watcher instance."""
    with patch("media_manager.watcher.file_mover.MediaCategorizer", return_value=mock_categorizer):
        return MediaWatcher(config)

@pytest.mark.asyncio
async def test_media_file_handler_initialization(config):
    """Test file handler initialization."""
    handler = MediaFileHandler(config)
    assert isinstance(handler.categorizer, MediaCategorizer)
    assert handler.config == config

@pytest.mark.asyncio
async def test_media_file_handler_new_file(file_handler, mock_categorizer):
    """Test handling new file."""
    filename = "Test.Movie.2024.mp4"
    
    with patch("os.path.exists", return_value=True), \
         patch("shutil.move") as mock_move:
        result = await file_handler.handle_file(filename)
        
        assert result.success
        mock_categorizer.process_file.assert_called_once_with(filename)
        mock_move.assert_called_once()

@pytest.mark.asyncio
async def test_media_file_handler_failed_processing(file_handler, mock_categorizer):
    """Test handling failed file processing."""
    mock_categorizer.process_file.return_value = MagicMock(
        success=False,
        error="Processing failed"
    )
    
    result = await file_handler.handle_file("test.mp4")
    assert not result.success
    assert "Processing failed" in result.error

@pytest.mark.asyncio
async def test_media_file_handler_duplicate_processing(file_handler):
    """Test handling duplicate file processing."""
    filename = "test.mp4"
    # First process
    await file_handler.handle_file(filename)
    # Second process
    result = await file_handler.handle_file(filename)
    
    assert not result.success
    assert "already processed" in result.error.lower()

@pytest.mark.asyncio
async def test_media_watcher_initialization(config):
    """Test media watcher initialization."""
    watcher = MediaWatcher(config)
    assert isinstance(watcher.file_handler, MediaFileHandler)
    assert watcher.config == config

@pytest.mark.asyncio
async def test_media_watcher_start_stop(watcher):
    """Test watcher start/stop."""
    # Start watching
    stop_event = asyncio.Event()
    task = asyncio.create_task(watcher.start_watching(stop_event))
    
    # Let it run briefly
    await asyncio.sleep(0.1)
    
    # Stop watching
    stop_event.set()
    await task

@pytest.mark.asyncio
async def test_media_watcher_process_existing(watcher):
    """Test processing existing files."""
    test_files = ["test1.mp4", "test2.mp4"]
    
    with patch("os.listdir", return_value=test_files), \
         patch("os.path.isfile", return_value=True):
        await watcher.process_existing_files()
        assert watcher.file_handler.processed_files == set(test_files)