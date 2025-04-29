"""TMDB API client module."""
import logging
from typing import Dict, Any, Optional
import aiohttp
import asyncio
from urllib.parse import quote

class TMDBClient:
    """Client for The Movie Database (TMDB) API."""
    
    BASE_URL = "https://api.themoviedb.org/3"
    
    def __init__(self, api_key: str):
        """
        Initialize TMDB client.
        
        Args:
            api_key: TMDB API key
        """
        self.api_key = api_key
        self.logger = logging.getLogger("TMDBClient")
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._rate_limit_remaining = 40
        self._rate_limit_reset = 0
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Make a request to TMDB API with rate limiting.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            Response JSON or None if request failed
        """
        if not params:
            params = {}
        params['api_key'] = self.api_key
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        async with self._lock:
            if self._rate_limit_remaining <= 0:
                wait_time = max(0, self._rate_limit_reset - asyncio.get_event_loop().time())
                if wait_time > 0:
                    self.logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
        
        try:
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                # Update rate limits
                self._rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 40))
                self._rate_limit_reset = float(response.headers.get('X-RateLimit-Reset', 0))
                
                if response.status == 429:  # Too Many Requests
                    retry_after = int(response.headers.get('Retry-After', 1))
                    self.logger.warning(f"Rate limit exceeded, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return await self._make_request(endpoint, params)
                    
                if response.status == 404:
                    return None
                    
                if response.status != 200:
                    error_json = await response.json()
                    error_msg = error_json.get('status_message', 'Unknown error')
                    self.logger.error(f"TMDB API error ({response.status}): {error_msg}")
                    return None
                    
                return await response.json()
                
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error accessing TMDB: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error making TMDB request: {str(e)}")
            return None

    async def search_movie(self, title: str, year: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Search for a movie.
        
        Args:
            title: Movie title
            year: Release year (optional)
            
        Returns:
            Movie information or None if not found
        """
        # Sanitize input
        query = quote(title)
        
        # Build search parameters
        params = {
            'query': query,
            'include_adult': 'false',
            'language': 'en-US',
            'page': 1
        }
        if year:
            params['year'] = year
            
        try:
            # Search for movies
            results = await self._make_request('search/movie', params)
            if not results or not results.get('results'):
                self.logger.info(f"No movies found for '{title}' ({year if year else 'any year'})")
                return None
                
            matches = results['results']
            
            # If year provided, filter exact matches first
            if year:
                exact_matches = [
                    m for m in matches 
                    if m.get('release_date', '').startswith(year)
                ]
                if exact_matches:
                    matches = exact_matches
            
            # Get the best match (usually the first result)
            best_match = matches[0]
            
            # Get full movie details
            movie_id = best_match['id']
            details = await self._make_request(f'movie/{movie_id}')
            
            if details:
                self.logger.info(
                    f"Found movie: {details['title']} ({details['release_date'][:4]}) "
                    f"[{details.get('vote_average', 'N/A')}/10]"
                )
                return details
            
            return best_match
            
        except Exception as e:
            self.logger.error(f"Error searching for movie '{title}': {str(e)}")
            return None

    async def search_tv_show(self, title: str) -> Optional[Dict[str, Any]]:
        """
        Search for a TV show.
        
        Args:
            title: Show title
            
        Returns:
            Show information or None if not found
        """
        # Sanitize input
        query = quote(title)
        
        try:
            # Search for TV shows
            results = await self._make_request('search/tv', {
                'query': query,
                'include_adult': 'false',
                'language': 'en-US',
                'page': 1
            })
            
            if not results or not results.get('results'):
                self.logger.info(f"No TV shows found for '{title}'")
                return None
            
            # Get the best match
            best_match = results['results'][0]
            
            # Get full show details
            show_id = best_match['id']
            details = await self._make_request(f'tv/{show_id}')
            
            if details:
                self.logger.info(
                    f"Found TV show: {details['name']} "
                    f"(First aired: {details.get('first_air_date', 'Unknown')[:4]}) "
                    f"[{details.get('vote_average', 'N/A')}/10]"
                )
                return details
                
            return best_match
            
        except Exception as e:
            self.logger.error(f"Error searching for TV show '{title}': {str(e)}")
            return None
            
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None