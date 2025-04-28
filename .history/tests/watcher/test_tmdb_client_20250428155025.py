"""Tests for the TMDB client component."""
import pytest
import aiohttp
from unittest import mock
from typing import Dict, Any
from media_manager.watcher.tmdb_client import TMDBClient

@pytest.fixture
def mock_response():
    """Mock successful API response."""
    return {
        "results": [
            {
                "id": 123,
                "title": "Test Movie",
                "name": "Test Show",
                "release_date": "2024-01-01",
                "first_air_date": "2024-01-01",
                "overview": "Test overview",
                "poster_path": "/test.jpg"
            }
        ]
    }

@pytest.fixture
def tmdb_client():
    """Create TMDBClient instance."""
    return TMDBClient("test_api_key")

@pytest.mark.asyncio
async def test_search_movie(tmdb_client, mock_response):
    """Test movie search."""
    with mock.patch("aiohttp.ClientSession.get") as mock_get:
        # Mock response
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = mock.AsyncMock(
            return_value=mock_response
        )
        
        # Search for movie
        result = await tmdb_client.search_movie("Test Movie", year=2024)
        
        # Verify request
        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        params = mock_get.call_args[1]["params"]
        
        assert "search/movie" in url
        assert params["api_key"] == "test_api_key"
        assert params["query"] == "Test Movie"
        assert params["year"] == 2024
        
        # Verify response parsing
        assert result == mock_response

@pytest.mark.asyncio
async def test_search_tv_show(tmdb_client, mock_response):
    """Test TV show search."""
    with mock.patch("aiohttp.ClientSession.get") as mock_get:
        # Mock response
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = mock.AsyncMock(
            return_value=mock_response
        )
        
        # Search for TV show
        result = await tmdb_client.search_tv_show("Test Show")
        
        # Verify request
        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        params = mock_get.call_args[1]["params"]
        
        assert "search/tv" in url
        assert params["api_key"] == "test_api_key"
        assert params["query"] == "Test Show"
        
        # Verify response parsing
        assert result == mock_response

@pytest.mark.asyncio
async def test_get_episode_details(tmdb_client, mock_response):
    """Test getting TV episode details."""
    with mock.patch("aiohttp.ClientSession.get") as mock_get:
        # Mock response
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = mock.AsyncMock(
            return_value={"id": 123, "name": "Test Episode"}
        )
        
        # Get episode details
        result = await tmdb_client.get_episode_details(123, 1, 1)
        
        # Verify request
        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        params = mock_get.call_args[1]["params"]
        
        assert "tv/123/season/1/episode/1" in url
        assert params["api_key"] == "test_api_key"
        
        # Verify response parsing
        assert result["id"] == 123
        assert result["name"] == "Test Episode"

@pytest.mark.asyncio
async def test_api_error_handling(tmdb_client):
    """Test handling of API errors."""
    with mock.patch("aiohttp.ClientSession.get") as mock_get:
        # Mock error response
        mock_get.return_value.__aenter__.return_value.status = 404
        mock_get.return_value.__aenter__.return_value.text = mock.AsyncMock(
            return_value="Not Found"
        )
        
        # Test error handling
        result = await tmdb_client.search_movie("Test Movie")
        assert result is None

@pytest.mark.asyncio
async def test_network_error_handling(tmdb_client):
    """Test handling of network errors."""
    with mock.patch("aiohttp.ClientSession.get") as mock_get:
        # Mock network error
        mock_get.side_effect = aiohttp.ClientError("Network error")
        
        # Test error handling
        result = await tmdb_client.search_movie("Test Movie")
        assert result is None

@pytest.mark.asyncio
async def test_invalid_json_handling(tmdb_client):
    """Test handling of invalid JSON responses."""
    with mock.patch("aiohttp.ClientSession.get") as mock_get:
        # Mock invalid JSON response
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = mock.AsyncMock(
            side_effect=ValueError("Invalid JSON")
        )
        
        # Test error handling
        result = await tmdb_client.search_movie("Test Movie")
        assert result is None