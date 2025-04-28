"""Tests for TMDB client."""
import pytest
import aiohttp
from unittest.mock import AsyncMock, patch
from media_manager.watcher.tmdb_client import TMDBClient

@pytest.fixture
def tmdb_config():
    """TMDB configuration for testing."""
    return {
        "tmdb": {
            "api_key": "test_key"
        }
    }

@pytest.fixture
def mock_response():
    """Create mock response."""
    mock = AsyncMock()
    mock.__aenter__.return_value.status = 200
    mock.__aenter__.return_value.json = AsyncMock(return_value={"results": [{"id": 1, "title": "Test Movie"}]})
    return mock

@pytest.fixture
def tmdb_client(tmdb_config):
    """Create TMDB client instance."""
    return TMDBClient(tmdb_config["tmdb"]["api_key"])

@pytest.mark.asyncio
async def test_search_movie(tmdb_client, mock_response):
    """Test movie search."""
    mock_response.__aenter__.return_value.json = AsyncMock(return_value={
        "results": [{
            "id": 1,
            "title": "Test Movie",
            "release_date": "2024-01-01",
            "overview": "Test overview",
            "poster_path": "/test.jpg"
        }]
    })
    
    with patch("aiohttp.ClientSession") as mock_session:
        mock_session.return_value = mock_response
        results = await tmdb_client.search_movie("test movie")
        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["title"] == "Test Movie"
        assert results[0]["year"] == "2024"

@pytest.mark.asyncio
async def test_search_tv_show(tmdb_client, mock_response):
    """Test TV show search."""
    mock_response.__aenter__.return_value.json = AsyncMock(return_value={
        "results": [{
            "id": 1,
            "name": "Test Show",
            "overview": "Test overview",
            "first_air_date": "2024-01-01",
            "poster_path": "/test.jpg"
        }]
    })
    
    with patch("aiohttp.ClientSession") as mock_session:
        mock_session.return_value = mock_response
        results = await tmdb_client.search_tv_show("test show")
        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["name"] == "Test Show"

@pytest.mark.asyncio
async def test_get_episode_details(tmdb_client, mock_response):
    """Test getting episode details."""
    mock_response.__aenter__.return_value.json = AsyncMock(return_value={
        "episode_number": 1,
        "season_number": 1,
        "name": "Test Episode",
        "overview": "Test overview",
        "air_date": "2024-01-01",
        "still_path": "/test.jpg"
    })
    
    with patch("aiohttp.ClientSession") as mock_session:
        mock_session.return_value = mock_response
        details = await tmdb_client.get_episode_details(1, 1, 1)
        assert details["episode_number"] == 1
        assert details["season_number"] == 1
        assert details["name"] == "Test Episode"

@pytest.mark.asyncio
async def test_api_error_handling(tmdb_client):
    """Test handling of API errors."""
    error_response = AsyncMock()
    error_response.__aenter__.return_value.status = 404
    error_response.__aenter__.return_value.text = AsyncMock(return_value="Not Found")
    
    with patch("aiohttp.ClientSession") as mock_session:
        mock_session.return_value = error_response
        results = await tmdb_client.search_movie("nonexistent")
        assert results == []

@pytest.mark.asyncio
async def test_network_error_handling(tmdb_client):
    """Test handling of network errors."""
    with patch("aiohttp.ClientSession", side_effect=aiohttp.ClientError):
        results = await tmdb_client.search_movie("test")
        assert results == []

@pytest.mark.asyncio
async def test_invalid_json_handling(tmdb_client):
    """Test handling of invalid JSON response."""
    mock = AsyncMock()
    mock.__aenter__.return_value.status = 200
    mock.__aenter__.return_value.json = AsyncMock(side_effect=ValueError)
    
    with patch("aiohttp.ClientSession") as mock_session:
        mock_session.return_value = mock
        results = await tmdb_client.search_movie("test")
        assert results == []