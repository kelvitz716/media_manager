"""Tests for media file mover functionality."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from media_manager.watcher.file_mover import MediaWatcher

@pytest.mark.asyncio
async def test_media_watcher_initialization(config, mock_categorizer, notification_service):
    """Test media watcher initialization."""
    watcher = MediaWatcher(config, mock_categorizer, notification_service)
    assert watcher.config == config
    assert watcher.categorizer == mock_categorizer
    assert watcher.notification_service == notification_service

@pytest.mark.asyncio
async def test_media_file_handler_initialization(config, mock_categorizer, notification_service):
    """Test media file handler initialization."""
    watcher = MediaWatcher(config, mock_categorizer, notification_service)
    test_file = "test.mkv"
    mock_categorizer.process_file.return_value = ("Movies", "Test Movie (2024)")
    
    await watcher._handle_media_file(test_file)
    mock_categorizer.process_file.assert_called_once_with(test_file)

@pytest.mark.asyncio
async def test_media_file_handler_new_file(config, mock_categorizer, notification_service):
    """Test handling new media file."""
    watcher = MediaWatcher(config, mock_categorizer, notification_service)
    test_file = "test_movie.mkv"
    mock_categorizer.process_file.return_value = ("Movies", "Test Movie (2024)")
    
    with patch('os.path.exists') as mock_exists, \
         patch('shutil.move') as mock_move:
        mock_exists.return_value = False
        await watcher._handle_media_file(test_file)
        mock_move.assert_called_once()

@pytest.mark.asyncio
async def test_media_file_handler_failed_processing(config, mock_categorizer, notification_service):
    """Test handling failed file processing."""
    watcher = MediaWatcher(config, mock_categorizer, notification_service)
    test_file = "invalid_file.mkv"
    mock_categorizer.process_file.return_value = (None, None)
    
    with patch('shutil.move') as mock_move:
        await watcher._handle_media_file(test_file)
        mock_move.assert_called_once()
        assert notification_service.bot.send_message.called

@pytest.mark.asyncio
async def test_media_file_handler_duplicate_processing(config, mock_categorizer, notification_service):
    """Test handling duplicate file processing."""
    watcher = MediaWatcher(config, mock_categorizer, notification_service)
    test_file = "duplicate.mkv"
    mock_categorizer.process_file.return_value = ("Movies", "Test Movie (2024)")
    
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = True
        await watcher._handle_media_file(test_file)
        assert notification_service.bot.send_message.called

@pytest.mark.asyncio
async def test_media_watcher_process_existing(config, mock_categorizer, notification_service):
    """Test processing existing files."""
    watcher = MediaWatcher(config, mock_categorizer, notification_service)
    
    with patch('os.walk') as mock_walk, \
         patch.object(watcher, '_handle_media_file') as mock_handle:
        mock_walk.return_value = [
            ('/downloads', [], ['test1.mkv', 'test2.mkv'])
        ]
        await watcher.process_existing_files()
        assert mock_handle.call_count == 2

@pytest.mark.asyncio
async def test_media_watcher_start_stop(config, mock_categorizer, notification_service):
    """Test watcher start and stop."""
    watcher = MediaWatcher(config, mock_categorizer, notification_service)
    
    with patch('asyncio.create_task') as mock_create_task:
        mock_task = AsyncMock()
        mock_create_task.return_value = mock_task
        
        await watcher.start()
        assert watcher._running
        mock_create_task.assert_called_once()
        
        await watcher.stop()
        assert not watcher._running
        mock_task.cancel.assert_called_once()