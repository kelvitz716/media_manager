"""Tests for TMDB client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from media_manager.watcher.tmdb_client import TMDBClient

@pytest.fixture
def tmdb_client():
    return TMDBClient("test_api_key")

@pytest.fixture
def mock_response():
    mock = AsyncMock()
    mock.status = 200
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock()
    return mock

async def test_search_movie(tmdb_client, mock_response):
    mock_data = {
        "results": [{
            "id": 1,
            "title": "Test Movie",
            "release_date": "2024-01-01",
            "overview": "Test overview",
            "poster_path": "/test.jpg"
        }]
    }
    mock_response.json = AsyncMock(return_value=mock_data)
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        results = await tmdb_client.search_movie("test")
        assert len(results) == 1
        assert results[0]["title"] == "Test Movie"
        assert results[0]["year"] == "2024"

async def test_search_tv_show(tmdb_client, mock_response):
    mock_data = {
        "results": [{
            "id": 1,
            "name": "Test Show",
            "overview": "Test overview",
            "first_air_date": "2024-01-01",
            "poster_path": "/test.jpg"
        }]
    }
    mock_response.json = AsyncMock(return_value=mock_data)
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        results = await tmdb_client.search_tv_show("test")
        assert len(results) == 1
        assert results[0]["name"] == "Test Show"

async def test_get_episode_details(tmdb_client, mock_response):
    mock_data = {
        "episode_number": 1,
        "season_number": 1,
        "name": "Test Episode",
        "overview": "Test overview",
        "air_date": "2024-01-01",
        "still_path": "/test.jpg"
    }
    mock_response.json = AsyncMock(return_value=mock_data)
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        details = await tmdb_client.get_episode_details(1, 1, 1)
        assert details["episode_number"] == 1
        assert details["season_number"] == 1
        assert details["name"] == "Test Episode"

async def test_api_error_handling(tmdb_client, mock_response):
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value="Not Found")
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        results = await tmdb_client.search_movie("test")
        assert results == []

async def test_network_error_handling(tmdb_client):
    with patch("aiohttp.ClientSession.get", side_effect=Exception("Network Error")):
        results = await tmdb_client.search_movie("test")
        assert results == []

async def test_invalid_json_handling(tmdb_client, mock_response):
    mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        results = await tmdb_client.search_movie("test")
        assert results == []