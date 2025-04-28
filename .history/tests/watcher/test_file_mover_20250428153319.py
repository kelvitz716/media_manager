"""Tests for the file watcher and mover components."""
import os
import asyncio
import pytest
from unittest import mock
from watchdog.events import FileCreatedEvent
from media_manager.watcher.file_mover import MediaFileHandler, MediaWatcher

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "paths": {
            "telegram_download_dir": "/tmp/downloads",
            "movies_dir": "/tmp/movies",
            "tv_shows_dir": "/tmp/tv_shows",
            "unmatched_dir": "/tmp/unmatched"
        },
        "process_existing_files": True
    }

@pytest.fixture
def mock_notification():
    """Mock notification service."""
    with mock.patch('media_manager.common.notification_service.NotificationService') as mock_notif:
        yield mock_notif.return_value

@pytest.fixture
def mock_categorizer():
    """Mock media categorizer."""
    with mock.patch('media_manager.watcher.categorizer.MediaCategorizer') as mock_cat:
        instance = mock_cat.return_value
        instance.process_file = mock.AsyncMock(return_value=True)
        instance.move_to_unmatched = mock.AsyncMock()
        yield instance

@pytest.mark.asyncio
async def test_media_file_handler_initialization(mock_categorizer):
    """Test initialization of MediaFileHandler."""
    handler = MediaFileHandler(mock_categorizer)
    
    assert handler.categorizer == mock_categorizer
    assert isinstance(handler._processing_files, set)
    assert handler._processing_files == set()
    assert handler._processing_lock is not None

@pytest.mark.asyncio
async def test_media_file_handler_new_file(mock_categorizer):
    """Test handling of new files."""
    handler = MediaFileHandler(mock_categorizer)
    
    # Create test event
    event = FileCreatedEvent("/tmp/test.mp4")
    
    # Mock wait_for_file_ready
    handler._wait_for_file_ready = mock.AsyncMock()
    
    # Handle the event
    handler.on_created(event)
    await asyncio.sleep(0.1)  # Allow async tasks to run
    
    # Verify processing sequence
    handler._wait_for_file_ready.assert_called_once_with("/tmp/test.mp4")
    mock_categorizer.process_file.assert_called_once_with("/tmp/test.mp4")
    mock_categorizer.move_to_unmatched.assert_not_called()

@pytest.mark.asyncio
async def test_media_file_handler_failed_processing(mock_categorizer):
    """Test handling of failed file processing."""
    handler = MediaFileHandler(mock_categorizer)
    mock_categorizer.process_file.return_value = False
    
    # Mock wait_for_file_ready
    handler._wait_for_file_ready = mock.AsyncMock()
    
    # Process a file
    await handler._handle_new_file("/tmp/test.mp4")
    
    # Verify unmatched move was called
    mock_categorizer.process_file.assert_called_once()
    mock_categorizer.move_to_unmatched.assert_called_once()

@pytest.mark.asyncio
async def test_media_file_handler_duplicate_processing(mock_categorizer):
    """Test prevention of duplicate file processing."""
    handler = MediaFileHandler(mock_categorizer)
    
    # Mock wait_for_file_ready
    handler._wait_for_file_ready = mock.AsyncMock()
    
    # Try to process same file twice simultaneously
    await asyncio.gather(
        handler._handle_new_file("/tmp/test.mp4"),
        handler._handle_new_file("/tmp/test.mp4")
    )
    
    # Verify file was only processed once
    mock_categorizer.process_file.assert_called_once()

@pytest.mark.asyncio
async def test_media_watcher_initialization(mock_config, mock_notification):
    """Test initialization of MediaWatcher."""
    with mock.patch('media_manager.watcher.categorizer.MediaCategorizer'), \
         mock.patch('watchdog.observers.Observer'):
        
        watcher = MediaWatcher(mock_config, mock_notification)
        
        assert watcher.config == mock_config
        assert watcher.notification == mock_notification
        assert watcher.handler is not None
        assert watcher.observer is not None

@pytest.mark.asyncio
async def test_media_watcher_start_stop(mock_config, mock_notification):
    """Test starting and stopping the watcher."""
    with mock.patch('media_manager.watcher.categorizer.MediaCategorizer'), \
         mock.patch('watchdog.observers.Observer') as mock_observer, \
         mock.patch('os.makedirs') as mock_makedirs:
        
        # Create watcher instance
        watcher = MediaWatcher(mock_config, mock_notification)
        mock_observer_instance = mock_observer.return_value
        
        # Test start
        watcher.start()
        
        # Verify directory creation and observer setup
        mock_makedirs.assert_called_once_with(mock_config["paths"]["telegram_download_dir"])
        mock_observer_instance.schedule.assert_called_once()
        mock_observer_instance.start.assert_called_once()
        
        # Test stop
        watcher.stop()
        mock_observer_instance.stop.assert_called_once()
        mock_observer_instance.join.assert_called_once()

@pytest.mark.asyncio
async def test_media_watcher_process_existing(mock_config, mock_notification, mock_categorizer):
    """Test processing of existing files."""
    with mock.patch('media_manager.watcher.categorizer.MediaCategorizer'), \
         mock.patch('watchdog.observers.Observer'), \
         mock.patch('os.listdir') as mock_listdir, \
         mock.patch('os.path.isfile', return_value=True):
        
        # Setup test files
        mock_listdir.return_value = ["test1.mp4", "test2.mp4"]
        
        # Create watcher instance
        watcher = MediaWatcher(mock_config, mock_notification)
        watcher.handler._handle_new_file = mock.AsyncMock()
        
        # Process existing files
        await watcher._process_existing_files()
        
        # Verify each file was processed
        assert watcher.handler._handle_new_file.call_count == 2
        watcher.handler._handle_new_file.assert_has_calls([
            mock.call(os.path.join(mock_config["paths"]["telegram_download_dir"], "test1.mp4")),
            mock.call(os.path.join(mock_config["paths"]["telegram_download_dir"], "test2.mp4"))
        ])