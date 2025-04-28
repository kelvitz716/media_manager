"""TMDB API client for fetching media metadata."""
import aiohttp
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class TMDBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        if params is None:
            params = {}
        params['api_key'] = self.api_key

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}{endpoint}", params=params) as response:
                    if response.status != 200:
                        logger.error(f"TMDB API error: {response.status} - {await response.text()}")
                        return {}
                    return await response.json()
        except Exception as e:
            logger.error(f"Error making TMDB request: {str(e)}")
            return {}

    async def search_movie(self, query: str) -> List[Dict[str, Any]]:
        data = await self._make_request("/search/movie", {"query": query})
        results = []
        
        for movie in data.get("results", []):
            if all(key in movie for key in ["id", "title", "release_date"]):
                results.append({
                    "id": movie["id"],
                    "title": movie["title"],
                    "year": movie["release_date"][:4] if movie["release_date"] else "",
                    "overview": movie.get("overview", ""),
                    "poster_path": movie.get("poster_path", "")
                })
        return results

    async def search_tv_show(self, query: str) -> List[Dict[str, Any]]:
        data = await self._make_request("/search/tv", {"query": query})
        results = []
        
        for show in data.get("results", []):
            if all(key in show for key in ["id", "name"]):
                results.append({
                    "id": show["id"],
                    "name": show["name"],
                    "overview": show.get("overview", ""),
                    "first_air_date": show.get("first_air_date", ""),
                    "poster_path": show.get("poster_path", "")
                })
        return results

    async def get_episode_details(self, show_id: int, season_number: int, episode_number: int) -> Dict[str, Any]:
        endpoint = f"/tv/{show_id}/season/{season_number}/episode/{episode_number}"
        data = await self._make_request(endpoint)
        
        if not data:
            return {}
            
        return {
            "episode_number": data.get("episode_number"),
            "season_number": data.get("season_number"),
            "name": data.get("name", ""),
            "overview": data.get("overview", ""),
            "air_date": data.get("air_date", ""),
            "still_path": data.get("still_path", "")
        }