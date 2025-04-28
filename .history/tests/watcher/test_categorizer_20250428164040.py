"""Tests for media file categorizer."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from media_manager.watcher.categorizer import MediaCategorizer
from media_manager.watcher.tmdb_client import TMDBClient

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
def mock_tmdb():
    """Mock TMDB client."""
    mock = AsyncMock(spec=TMDBClient)
    mock.search_movie.return_value = [{
        "id": 1,
        "title": "Test Movie",
        "release_date": "2024-01-01"
    }]
    mock.search_tv_show.return_value = [{
        "id": 1,
        "name": "Test Show"
    }]
    mock.get_episode_details.return_value = {
        "name": "Test Episode",
        "episode_number": 1,
        "season_number": 1
    }
    return mock

@pytest.fixture
def categorizer(config, mock_tmdb):
    """Create categorizer instance."""
    with patch("media_manager.watcher.categorizer.TMDBClient", return_value=mock_tmdb):
        return MediaCategorizer(config)

@pytest.mark.asyncio
async def test_parse_movie_filename():
    """Test parsing movie filenames."""
    test_cases = [
        ("Test.Movie.2024.1080p.mp4", ("Test Movie", "2024")),
        ("Test Movie (2024).mkv", ("Test Movie", "2024")),
        ("Test.Movie.2024.BluRay.x264.mp4", ("Test Movie", "2024")),
        ("invalid_movie.mp4", (None, None))
    ]
    
    for filename, expected in test_cases:
        title, year = MediaCategorizer.parse_movie_filename(filename)
        assert (title, year) == expected

@pytest.mark.asyncio
async def test_parse_tv_show_filename():
    """Test parsing TV show filenames."""
    test_cases = [
        ("Test.Show.S01E01.1080p.mp4", ("Test Show", 1, 1)),
        ("Test Show - 1x01.mkv", ("Test Show", 1, 1)),
        ("Test.Show.101.HDTV.x264.mp4", ("Test Show", 1, 1)),
        ("invalid_show.mp4", (None, None, None))
    ]
    
    for filename, expected in test_cases:
        show, season, episode = MediaCategorizer.parse_tv_show_filename(filename)
        assert (show, season, episode) == expected

@pytest.mark.asyncio
async def test_process_movie(categorizer, mock_tmdb):
    """Test movie processing."""
    filename = "Test.Movie.2024.1080p.mp4"
    result = await categorizer.process_movie(filename)
    
    assert result.success
    assert "Test Movie (2024)" in result.destination
    mock_tmdb.search_movie.assert_called_once_with("Test Movie", year="2024")

@pytest.mark.asyncio
async def test_process_tv_show(categorizer, mock_tmdb):
    """Test TV show processing."""
    filename = "Test.Show.S01E01.1080p.mp4"
    result = await categorizer.process_tv_show(filename)
    
    assert result.success
    assert "Test Show/Season 1" in result.destination
    mock_tmdb.search_tv_show.assert_called_once_with("Test Show")

@pytest.mark.asyncio
async def test_process_file(categorizer):
    """Test general file processing."""
    # Test movie
    movie_result = await categorizer.process_file("Test.Movie.2024.1080p.mp4")
    assert movie_result.success
    assert movie_result.media_type == "movie"
    
    # Test TV show
    tv_result = await categorizer.process_file("Test.Show.S01E01.1080p.mp4")
    assert tv_result.success
    assert tv_result.media_type == "tv_show"

@pytest.mark.asyncio
async def test_process_file_no_match(categorizer):
    """Test processing file with no match."""
    result = await categorizer.process_file("invalid_file.mp4")
    assert not result.success
    assert result.media_type == "unknown"

@pytest.mark.asyncio
async def test_move_to_unmatched(categorizer):
    """Test moving file to unmatched directory."""
    filename = "invalid_file.mp4"
    
    with patch("os.path.exists", return_value=True), \
         patch("shutil.move") as mock_move:
        await categorizer.move_to_unmatched(filename)
        mock_move.assert_called_once()
        assert categorizer.config["paths"]["unmatched_dir"] in mock_move.call_args[0][1]

@pytest.mark.asyncio
async def test_error_handling(categorizer, mock_tmdb):
    """Test error handling during processing."""
    # Test TMDB API error
    mock_tmdb.search_movie.side_effect = Exception("API Error")
    result = await categorizer.process_movie("Test.Movie.2024.1080p.mp4")
    assert not result.success
    assert "API Error" in result.error
    
    # Test move error
    with patch("shutil.move", side_effect=OSError("Move Error")):
        result = await categorizer.move_to_unmatched("test.mp4")
        assert not result.success
        assert "Move Error" in result.error