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

    async def search_movie(self, title: str, year: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for a movie by title and optionally year."""
        self.logger.debug(f"Searching for movie: {title} ({year if year else 'no year'})")
        
        # First try with year if provided
        if year:
            query = f"{title} {year}"
            data = await self._make_request("/search/movie", {"query": query})
            results = self._filter_movie_results(data.get("results", []), title, year)
            
            if results:
                self.logger.debug(f"Found {len(results)} results with year filter")
                return results
                
            # If no results with year, try without year
            self.logger.debug("No results with year, trying without year")
            
        # Search without year
        data = await self._make_request("/search/movie", {"query": title})
        results = self._filter_movie_results(data.get("results", []), title)
        self.logger.debug(f"Found {len(results)} results without year filter")
        return results
        
    def _filter_movie_results(self, results: List[Dict], title: str, year: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filter and format movie results."""
        filtered = []
        
        for movie in results:
            if not all(key in movie for key in ["id", "title", "release_date"]):
                continue
                
            movie_year = movie["release_date"][:4] if movie["release_date"] else ""
            
            # Score the match
            title_similarity = self._get_title_similarity(title.lower(), movie["title"].lower())
            year_match = not year or movie_year == year
            
            # Include if title is similar enough and year matches (if provided)
            if title_similarity >= 0.8 and (not year or year_match):
                filtered.append({
                    "id": movie["id"],
                    "title": movie["title"],
                    "release_date": movie["release_date"],
                    "overview": movie.get("overview", ""),
                    "poster_path": movie.get("poster_path", "")
                })
                
        return filtered
        
    def _get_title_similarity(self, a: str, b: str) -> float:
        """Get similarity score between two titles."""
        # Remove common words and punctuation
        common_words = {'the', 'a', 'an', 'and', '&'}
        a_words = set(word.strip('.,!?()[]{}') for word in a.split()) - common_words
        b_words = set(word.strip('.,!?()[]{}') for word in b.split()) - common_words
        
        if not a_words or not b_words:
            return 0.0
            
        # Calculate Jaccard similarity
        intersection = len(a_words & b_words)
        union = len(a_words | b_words)
        return intersection / union if union > 0 else 0.0

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