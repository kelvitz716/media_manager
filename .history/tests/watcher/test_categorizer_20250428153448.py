"""Tests for the media categorizer component."""
import os
import pytest
from unittest import mock
from typing import Dict, Any, Tuple
from media_manager.watcher.categorizer import MediaCategorizer

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "tmdb": {
            "api_key": "test_api_key"
        },
        "paths": {
            "movies_dir": "/tmp/movies",
            "tv_shows_dir": "/tmp/tv_shows",
            "unmatched_dir": "/tmp/unmatched"
        }
    }

@pytest.fixture
def mock_notification():
    """Mock notification service."""
    with mock.patch('media_manager.common.notification_service.NotificationService') as mock_notif:
        instance = mock_notif.return_value
        instance.notify = mock.AsyncMock()
        yield instance

@pytest.fixture
def mock_tmdb():
    """Mock TMDb client."""
    with mock.patch('media_manager.watcher.tmdb_client.TMDBClient') as mock_client:
        instance = mock_client.return_value
        instance.search_movie = mock.AsyncMock()
        instance.search_tv = mock.AsyncMock()
        yield instance

@pytest.fixture
def categorizer(mock_config, mock_notification):
    """Create MediaCategorizer instance."""
    return MediaCategorizer(mock_config, mock_notification)

@pytest.mark.asyncio
async def test_parse_movie_filename(categorizer):
    """Test parsing of movie filenames."""
    # Test with year in filename
    result = categorizer._parse_filename("The.Matrix.1999.mp4")
    assert result[0] == "movie"
    assert result[1]["title"] == "The Matrix"
    assert result[1]["year"] == "1999"
    
    # Test with year in parentheses
    result = categorizer._parse_filename("The Matrix (1999).mp4")
    assert result[0] == "movie"
    assert result[1]["title"] == "The Matrix"
    assert result[1]["year"] == "1999"
    
    # Test with invalid format
    result = categorizer._parse_filename("Just.A.Movie.mp4")
    assert result[0] is None
    assert result[1] is None

@pytest.mark.asyncio
async def test_parse_tv_show_filename(categorizer):
    """Test parsing of TV show filenames."""
    # Test SxxExx format
    result = categorizer._parse_filename("Breaking.Bad.S01E05.mp4")
    assert result[0] == "tv"
    assert result[1]["show"] == "Breaking Bad"
    assert result[1]["season"] == "01"
    assert result[1]["episode"] == "05"
    
    # Test xxXxx format
    result = categorizer._parse_filename("Breaking.Bad.1x05.mp4")
    assert result[0] == "tv"
    assert result[1]["show"] == "Breaking Bad"
    assert result[1]["season"] == "1"
    assert result[1]["episode"] == "05"

@pytest.mark.asyncio
async def test_process_movie(categorizer, mock_tmdb):
    """Test movie processing."""
    # Mock successful TMDB response
    mock_tmdb.search_movie.return_value = {
        "results": [{
            "id": 123,
            "title": "The Matrix",
            "release_date": "1999-03-31",
            "overview": "A computer programmer discovers reality isn't real"
        }]
    }
    
    success = await categorizer._process_movie("/tmp/test.mp4", {
        "title": "The Matrix",
        "year": "1999"
    })
    
    assert success is True
    mock_tmdb.search_movie.assert_called_once_with("The Matrix", year="1999")

@pytest.mark.asyncio
async def test_process_tv_show(categorizer, mock_tmdb):
    """Test TV show processing."""
    # Mock successful TMDB response
    mock_tmdb.search_tv.return_value = {
        "results": [{
            "id": 456,
            "name": "Breaking Bad",
            "first_air_date": "2008-01-20",
            "overview": "A chemistry teacher turns to crime"
        }]
    }
    
    success = await categorizer._process_tv_show("/tmp/test.mp4", {
        "show": "Breaking Bad",
        "season": "1",
        "episode": "5"
    })
    
    assert success is True
    mock_tmdb.search_tv.assert_called_once_with("Breaking Bad")

@pytest.mark.asyncio
async def test_process_file(categorizer):
    """Test full file processing pipeline."""
    # Mock internal methods
    categorizer._parse_filename = mock.MagicMock(return_value=("movie", {
        "title": "The Matrix",
        "year": "1999"
    }))
    categorizer._process_movie = mock.AsyncMock(return_value=True)
    
    # Process a file
    success = await categorizer.process_file("/tmp/test.mp4")
    
    assert success is True
    categorizer._parse_filename.assert_called_once_with("test.mp4")
    categorizer._process_movie.assert_called_once()

@pytest.mark.asyncio
async def test_process_file_no_match(categorizer, mock_notification):
    """Test processing of unrecognized files."""
    # Mock failed parsing
    categorizer._parse_filename = mock.MagicMock(return_value=(None, None))
    
    # Process unrecognized file
    success = await categorizer.process_file("/tmp/unknown.mp4")
    
    assert success is False
    mock_notification.notify.assert_called_once()
    assert "manually" in mock_notification.notify.call_args[0][0]

@pytest.mark.asyncio
async def test_move_to_unmatched(categorizer):
    """Test moving files to unmatched directory."""
    with mock.patch('os.makedirs') as mock_makedirs, \
         mock.patch('shutil.move') as mock_move:
        
        await categorizer.move_to_unmatched("/tmp/test.mp4")
        
        mock_makedirs.assert_called_once_with(categorizer.config["paths"]["unmatched_dir"], exist_ok=True)
        mock_move.assert_called_once_with("/tmp/test.mp4", os.path.join(categorizer.config["paths"]["unmatched_dir"], "test.mp4"))

@pytest.mark.asyncio
async def test_error_handling(categorizer, mock_notification):
    """Test error handling during processing."""
    # Mock processing error
    categorizer._parse_filename = mock.MagicMock(side_effect=Exception("Test error"))
    
    # Process file that will raise error
    success = await categorizer.process_file("/tmp/test.mp4")
    
    assert success is False
    mock_notification.notify.assert_called_once()
    assert "Error" in mock_notification.notify.call_args[0][0]