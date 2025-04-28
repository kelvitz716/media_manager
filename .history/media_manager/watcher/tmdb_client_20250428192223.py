"""TMDB API client for fetching media metadata."""
import aiohttp
import logging


class TMDBClient:
    def __init__(self, api_key):
        """Initialize the TMDB client with API key."""
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    async def _make_request(self, endpoint, params=None):
        """Make a request to the TMDB API."""
        if params is None:
            params = {}
        params['api_key'] = self.api_key
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logging.error(f"TMDB request failed: {await response.text()}")
                        return None
        except Exception as e:
            logging.error(f"TMDB request error: {str(e)}")
            return None

    async def search_movie(self, query):
        """Search for a movie."""
        result = await self._make_request("/search/movie", {"query": query})
        if not result:
            return []
        
        movies = []
        for movie in result.get("results", []):
            movies.append({
                "id": movie["id"],
                "title": movie["title"],
                "year": movie.get("release_date", "")[:4],
                "overview": movie.get("overview", ""),
                "poster_path": movie.get("poster_path", "")
            })
        return movies

    async def search_tv_show(self, query):
        """Search for a TV show."""
        result = await self._make_request("/search/tv", {"query": query})
        if not result:
            return []
        
        shows = []
        for show in result.get("results", []):
            shows.append({
                "id": show["id"],
                "name": show["name"],
                "overview": show.get("overview", ""),
                "first_air_date": show.get("first_air_date", ""),
                "poster_path": show.get("poster_path", "")
            })
        return shows

    async def get_episode_details(self, show_id, season_number, episode_number):
        """Get details for a specific episode."""
        endpoint = f"/tv/{show_id}/season/{season_number}/episode/{episode_number}"
        result = await self._make_request(endpoint)
        if not result:
            return {}
        
        return {
            "episode_number": result["episode_number"],
            "season_number": result["season_number"],
            "name": result["name"],
            "overview": result.get("overview", ""),
            "air_date": result.get("air_date", ""),
            "still_path": result.get("still_path", "")
        }