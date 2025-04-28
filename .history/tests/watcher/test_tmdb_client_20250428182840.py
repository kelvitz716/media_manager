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
    mock.status = 200
    mock.json = AsyncMock(return_value={"results": [{"id": 1, "title": "Test Movie"}]})
    return mock

@pytest.fixture
def tmdb_client(tmdb_config):
    """Create TMDB client instance."""
    return TMDBClient(tmdb_config["tmdb"]["api_key"])

@pytest.mark.asyncio
async def test_search_movie(tmdb_client, mock_response):
    """Test movie search."""
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        results = await tmdb_client.search_movie("test movie")
        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["title"] == "Test Movie"

@pytest.mark.asyncio
async def test_search_tv_show(tmdb_client, mock_response):
    """Test TV show search."""
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        results = await tmdb_client.search_tv_show("test show")
        assert len(results) == 1
        assert results[0]["id"] == 1

@pytest.mark.asyncio
async def test_get_episode_details(tmdb_client, mock_response):
    """Test getting episode details."""
    mock_response.json.return_value = {
        "episode_number": 1,
        "season_number": 1,
        "name": "Test Episode"
    }
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        details = await tmdb_client.get_episode_details(1, 1, 1)
        assert details["episode_number"] == 1
        assert details["season_number"] == 1
        assert details["name"] == "Test Episode"

@pytest.mark.asyncio
async def test_api_error_handling(tmdb_client):
    """Test handling of API errors."""
    error_response = AsyncMock()
    error_response.status = 404
    error_response.text = AsyncMock(return_value="Not Found")
    
    with patch("aiohttp.ClientSession.get", return_value=error_response):
        results = await tmdb_client.search_movie("nonexistent")
        assert results == []

@pytest.mark.asyncio
async def test_network_error_handling(tmdb_client):
    """Test handling of network errors."""
    with patch("aiohttp.ClientSession.get", side_effect=aiohttp.ClientError):
        results = await tmdb_client.search_movie("test")
        assert results == []

@pytest.mark.asyncio
async def test_invalid_json_handling(tmdb_client):
    """Test handling of invalid JSON response."""
    mock = AsyncMock()
    mock.status = 200
    mock.json = AsyncMock(side_effect=ValueError)
    
    with patch("aiohttp.ClientSession.get", return_value=mock):
        results = await tmdb_client.search_movie("test")
        assert results == []