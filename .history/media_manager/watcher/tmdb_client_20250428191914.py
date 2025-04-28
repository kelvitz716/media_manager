"""TMDB API client for fetching media metadata."""
import aiohttp
import logging
from typing import Dict, Any, Optional, List
import urllib.parse

class TMDBClient:
    """Client for The Movie Database API."""
    
    BASE_URL = "https://api.themoviedb.org/3"
    
    def __init__(self, api_key: str):
        """
        Initialize TMDB client.
        
        Args:
            api_key: TMDB API key
        """
        self.api_key = api_key
        self.logger = logging.getLogger("TMDBClient")
        
    async def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Make API request to TMDB."""
        if params is None:
            params = {}
        params['api_key'] = self.api_key
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        self.logger.error(
                            f"TMDB API error: {response.status} - {await response.text()}"
                        )
                        return None
                        
        except Exception as e:
            self.logger.error(f"TMDB request error: {e}")
            return None
            
    async def search_movie(self, title: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for a movie.
        
        Args:
            title: Movie title
            year: Optional release year
            
        Returns:
            List of movie information dictionaries
        """
        # Clean up title
        query = urllib.parse.quote(title.replace('.', ' '))
        
        params = {
            'query': query,
            'language': 'en-US',
            'page': 1,
            'include_adult': False
        }
        if year:
            params['year'] = year
            
        results = await self._request('search/movie', params) or {}
        
        if results.get('results'):
            return [{
                'id': movie['id'],
                'title': movie['title'],
                'year': movie['release_date'][:4] if movie.get('release_date') else None,
                'overview': movie.get('overview'),
                'poster_path': movie.get('poster_path')
            } for movie in results['results']]
        return []
        
    async def search_tv_show(self, title: str) -> List[Dict[str, Any]]:
        """
        Search for a TV show.
        
        Args:
            title: Show title
            
        Returns:
            List of show information dictionaries
        """
        # Clean up title
        query = urllib.parse.quote(title.replace('.', ' '))
        
        params = {
            'query': query,
            'language': 'en-US',
            'page': 1
        }
        
        results = await self._request('search/tv', params) or {}
        
        if results.get('results'):
            return [{
                'id': show['id'],
                'name': show['name'],
                'overview': show.get('overview'),
                'first_air_date': show.get('first_air_date'),
                'poster_path': show.get('poster_path')
            } for show in results['results']]
        return []
        
    async def get_episode_details(self, show_id: int, season: int, episode: int) -> Dict[str, Any]:
        """
        Get TV episode details.
        
        Returns:
            Episode details dictionary or empty dict if not found
        """
        results = await self._request(f'tv/{show_id}/season/{season}/episode/{episode}') or {}
        
        return {
            'episode_number': results.get('episode_number'),
            'season_number': results.get('season_number'),
            'name': results.get('name'),
            'overview': results.get('overview'),
            'air_date': results.get('air_date'),
            'still_path': results.get('still_path'),
            'vote_average': results.get('vote_average'),
            'vote_count': results.get('vote_count')
        } if results else {}