"""Tests for media categorizer module."""
import pytest
from unittest.mock import patch, AsyncMock
from media_manager.watcher.categorizer import MediaCategorizer

@pytest.fixture
def config():
    """Create test configuration."""
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
    """Create mocked TMDB client."""
    return AsyncMock()

@pytest.fixture
def mock_notifier():
    """Create mocked notification service."""
    notifier = AsyncMock()
    notifier.notify = AsyncMock()
    return notifier

@pytest.fixture
def categorizer(config, mock_tmdb, mock_notifier):
    """Create categorizer instance."""
    with patch("media_manager.watcher.categorizer.TMDBClient", return_value=mock_tmdb):
        return MediaCategorizer(config, mock_notifier)

@pytest.mark.asyncio
async def test_parse_movie_filename():
    """Test parsing movie filenames."""
    test_cases = [
        ("The.Movie.2024.1080p.WEBRip.x264-GROUP", "The Movie", "2024"),
        ("Another.Movie.2023.720p.BluRay-GROUP", "Another Movie", "2023"),
    ]
    
    for filename, expected_title, expected_year in test_cases:
        title, year = MediaCategorizer.parse_movie_filename(filename)
        assert title == expected_title
        assert year == expected_year

@pytest.mark.asyncio
async def test_parse_tv_show_filename():
    """Test parsing TV show filenames."""
    test_cases = [
        ("Show.Name.S01E02.720p.WEBRip.x264-GROUP", "Show Name", 1, 2),
        ("Another.Show.S05E15.1080p.BluRay-GROUP", "Another Show", 5, 15),
    ]
    
    for filename, expected_title, expected_season, expected_episode in test_cases:
        title, season, episode = MediaCategorizer.parse_tv_show_filename(filename)
        assert title == expected_title
        assert season == expected_season
        assert episode == expected_episode

@pytest.mark.asyncio
async def test_process_movie(categorizer, mock_tmdb):
    """Test processing movie files."""
    filename = "The.Movie.2024.1080p.WEBRip.x264-GROUP"
    mock_tmdb.search_movie.return_value = {"id": 1, "title": "The Movie"}
    
    result = await categorizer.process_movie(filename)
    assert result
    mock_tmdb.search_movie.assert_called_once_with("The Movie", "2024")

@pytest.mark.asyncio
async def test_process_tv_show(categorizer, mock_tmdb):
    """Test processing TV show files."""
    filename = "Show.Name.S01E02.720p.WEBRip.x264-GROUP"
    mock_tmdb.search_tv_show.return_value = {"id": 1, "name": "Show Name"}
    mock_tmdb.get_episode_details.return_value = {"id": 2, "name": "Episode 2"}
    
    result = await categorizer.process_tv_show(filename)
    assert result
    mock_tmdb.search_tv_show.assert_called_once_with("Show Name")

@pytest.mark.asyncio
async def test_process_file(categorizer, mock_tmdb):
    """Test processing media files."""
    movie_file = "The.Movie.2024.1080p.WEBRip.x264-GROUP"
    tv_show_file = "Show.Name.S01E02.720p.WEBRip.x264-GROUP"
    
    mock_tmdb.search_movie.return_value = {"id": 1, "title": "The Movie"}
    mock_tmdb.search_tv_show.return_value = {"id": 2, "name": "Show Name"}
    mock_tmdb.get_episode_details.return_value = {"id": 3, "name": "Episode 2"}
    
    await categorizer.process_file(movie_file)
    await categorizer.process_file(tv_show_file)
    
    mock_tmdb.search_movie.assert_called_once()
    mock_tmdb.search_tv_show.assert_called_once()

@pytest.mark.asyncio
async def test_process_file_no_match(categorizer, mock_tmdb, mock_notifier):
    """Test processing file with no match."""
    filename = "Unknown.File.2024.1080p.WEBRip.x264-GROUP"
    mock_tmdb.search_movie.return_value = None
    mock_tmdb.search_tv_show.return_value = None
    
    await categorizer.process_file(filename)
    mock_notifier.notify.assert_called_once()

@pytest.mark.asyncio
async def test_move_to_unmatched(categorizer, mock_notifier):
    """Test moving file to unmatched directory."""
    filename = "Unknown.File.mkv"
    await categorizer.move_to_unmatched(filename)
    mock_notifier.notify.assert_called_once()

@pytest.mark.asyncio
async def test_error_handling(categorizer, mock_tmdb, mock_notifier):
    """Test error handling during processing."""
    filename = "Test.Movie.2024.1080p.WEBRip.x264-GROUP"
    mock_tmdb.search_movie.side_effect = Exception("API Error")
    
    await categorizer.process_file(filename)
    mock_notifier.notify.assert_called_once()