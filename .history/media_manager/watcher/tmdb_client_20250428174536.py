"""TMDB API client for fetching media metadata."""
import aiohttp
import logging
from typing import Dict, Any, Optional
import urllib.parse

class TMDBClient:
    """Client for The Movie Database API."""
    
    BASE_URL = "https://api.themoviedb.org/3"
    
    def __init__(self, api_key: str):
        """Initialize TMDB client."""
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
                        return {}
                        
        except Exception as e:
            self.logger.error(f"TMDB request error: {e}")
            return {}
            
    async def search_movie(self, title: str, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Search for a movie.
        
        Args:
            title: Movie title
            year: Optional release year
            
        Returns:
            Movie information or empty dict if not found
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
            
        results = await self._request('search/movie', params)
        
        if results and results.get('results'):
            # Get first match
            movie = results['results'][0]
            return {
                'id': movie['id'],
                'title': movie['title'],
                'year': movie['release_date'][:4] if movie.get('release_date') else None,
                'overview': movie.get('overview'),
                'poster_path': movie.get('poster_path')
            }
        return {}
        
    async def search_tv_show(self, title: str) -> Dict[str, Any]:
        """
        Search for a TV show.
        
        Args:
            title: Show title
            
        Returns:
            Show information or empty dict if not found
        """
        # Clean up title
        query = urllib.parse.quote(title.replace('.', ' '))
        
        params = {
            'query': query,
            'language': 'en-US',
            'page': 1
        }
        
        results = await self._request('search/tv', params)
        
        if results and results.get('results'):
            # Get first match
            show = results['results'][0]
            return {
                'id': show['id'],
                'name': show['name'],
                'overview': show.get('overview'),
                'first_air_date': show.get('first_air_date'),
                'poster_path': show.get('poster_path')
            }
        return {}
        
    async def get_episode_details(self, show_id: int, season: int, episode: int) -> Dict[str, Any]:
        """
        Get TV episode details.
        
        Returns:
            Episode details or empty dict if not found
        """
        results = await self._request(f'tv/{show_id}/season/{season}/episode/{episode}')
        
        if results:
            return {
                'name': results.get('name'),
                'overview': results.get('overview'),
                'air_date': results.get('air_date'),
                'still_path': results.get('still_path')
            }
        return {}