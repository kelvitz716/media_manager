"""File categorization and processing module."""
import os
import re
import shutil
import logging
from typing import Dict, Any, Optional, Tuple
from media_manager.watcher.tmdb_client import TMDBClient
from media_manager.common.notification_service import NotificationService

class MediaCategorizer:
    """Handles media file categorization and organization."""
    
    # Class-level regex patterns
    MOVIE_PATTERNS = [
        r'^(?P<title>.+?)[\. ](?P<year>19\d{2}|20\d{2})',
        r'^(?P<title>.+?)[\. ]\((?P<year>19\d{2}|20\d{2})\)'
    ]
    TV_PATTERNS = [
        r'^(?P<show>.+?)[\. ]S(?P<season>\d{1,2})E(?P<episode>\d{1,2})',
        r'^(?P<show>.+?)[\. ](?P<season>\d{1,2})x(?P<episode>\d{1,2})'
    ]
    
    def __init__(self, config_manager, notification_service: NotificationService):
        """Initialize categorizer."""
        self.config_manager = config_manager
        self.logger = logging.getLogger("MediaCategorizer")
        self.notification = notification_service
        
        # Validate TMDB API key
        tmdb_api_key = self.config_manager["tmdb"]["api_key"]
        if not tmdb_api_key or tmdb_api_key == "YOUR_TMDB_API_KEY":
            self.logger.error("TMDB API key not configured")
            self.tmdb = None
        else:
            self.tmdb = TMDBClient(tmdb_api_key)
            self.logger.info("TMDB client initialized successfully")

    @staticmethod
    def parse_movie_filename(filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse movie filename to extract title and year.
        
        Args:
            filename: Movie filename
            
        Returns:
            Tuple of (title, year) or (None, None) if no match
        """
        for pattern in MediaCategorizer.MOVIE_PATTERNS:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                groups = match.groupdict()
                title = groups["title"].replace(".", " ").strip()
                return title, groups["year"]
        return None, None
        
    @staticmethod
    def parse_tv_show_filename(filename: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Parse TV show filename to extract show name, season, and episode.
        
        Args:
            filename: TV show filename
            
        Returns:
            Tuple of (show_name, season_number, episode_number) or (None, None, None) if no match
        """
        for pattern in MediaCategorizer.TV_PATTERNS:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                groups = match.groupdict()
                show = groups["show"].replace(".", " ").strip()
                return show, int(groups["season"]), int(groups["episode"])
        return None, None, None
        
    async def process_file(self, file_path: str) -> bool:
        """Process and categorize a media file."""
        try:
            if not self.tmdb:
                self.logger.error("Cannot process file: TMDB client not initialized")
                await self.notification.notify(
                    "Media categorization disabled: TMDB API key not configured",
                    level="error"
                )
                return False

            filename = os.path.basename(file_path)
            self.logger.info(f"Starting categorization process for: {filename}")
            
            # Verify file exists and is readable
            if not os.path.exists(file_path):
                self.logger.error(f"File does not exist: {file_path}")
                return False
                
            if not os.access(file_path, os.R_OK):
                self.logger.error(f"File is not readable: {file_path}")
                return False
            
            # Try as movie first
            self.logger.debug(f"Attempting to parse as movie: {filename}")
            title, year = self.parse_movie_filename(filename)
            if title and year:
                self.logger.debug(f"Parsed as movie: {title} ({year})")
                success = await self.process_movie(file_path)
                if success:
                    self.logger.info(f"Successfully processed movie: {filename}")
                return success
                
            # Try as TV show
            self.logger.debug(f"Attempting to parse as TV show: {filename}")
            show, season, episode = self.parse_tv_show_filename(filename)
            if show and season and episode:
                self.logger.debug(f"Parsed as TV show: {show} S{season:02d}E{episode:02d}")
                success = await self.process_tv_show(file_path)
                if success:
                    self.logger.info(f"Successfully processed TV show: {filename}")
                return success
                
            # Unable to parse
            self.logger.warning(f"Unable to parse filename: {filename}")
            await self.notification.notify(
                f"Unable to automatically categorize: {filename}\n"
                "Please use /categorize to process manually.",
                level="warning"
            )
            self.logger.info(f"Moving {filename} to unmatched directory")
            await self.move_to_unmatched(file_path)
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
            await self.notification.notify(
                f"Error processing file: {str(e)}",
                level="error"
            )
            return False
            
    async def process_movie(self, file_path: str) -> bool:
        """Process a movie file."""
        try:
            filename = os.path.basename(file_path)
            title, year = self.parse_movie_filename(filename)
            if not title:
                raise ValueError(f"Could not parse movie filename: {filename}")
            
            # Get movie details from TMDB
            results = await self.tmdb.search_movie(title, year)
            
            if not results:
                await self.notification.notify(
                    f"Could not find movie info for: {title} ({year if year else 'unknown year'})",
                    level="warning"
                )
                return False
                
            movie_info = results[0]  # Use first result
            
            # Create destination path
            movie_dir = os.path.join(
                self.config_manager["paths"]["movies_dir"],
                f"{movie_info['title']} ({movie_info['release_date'][:4]})"
            )
            os.makedirs(movie_dir, exist_ok=True)
            
            # Move file
            new_path = os.path.join(movie_dir, filename)
            shutil.move(file_path, new_path)
            
            await self.notification.notify(
                f"Processed movie: {movie_info['title']} ({movie_info['release_date'][:4]})",
                level="info"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing movie {file_path}: {e}")
            await self.notification.notify(
                f"Error processing movie {filename}: {str(e)}",
                level="error"
            )
            return False
            
    async def process_tv_show(self, file_path: str) -> bool:
        """Process a TV show episode."""
        try:
            filename = os.path.basename(file_path)
            show, season, episode = self.parse_tv_show_filename(filename)
            if not show or not season or not episode:
                raise ValueError(f"Could not parse TV show filename: {filename}")
            
            # Get show details from TMDB
            results = await self.tmdb.search_tv_show(show)
            
            if not results or len(results) == 0:
                await self.notification.notify(
                    f"Could not find TV show info for: {show}",
                    level="warning"
                )
                await self.move_to_unmatched(file_path)
                return False
                
            show_info = results[0]  # Use first result
            
            # Get episode details
            episode_info = await self.tmdb.get_episode_details(
                show_info["id"], 
                season, 
                episode
            )
            
            if not episode_info:
                await self.notification.notify(
                    f"Could not find episode info for: {show} S{season:02d}E{episode:02d}",
                    level="warning"
                )
                await self.move_to_unmatched(file_path)
                return False
                
            # Create destination path
            tv_dir = self.config_manager["paths"]["tv_shows_dir"]
            show_dir = os.path.join(tv_dir, show_info["name"])
            season_dir = os.path.join(show_dir, f"Season {season:02d}")
            os.makedirs(season_dir, exist_ok=True)
            
            # Move file
            new_path = os.path.join(season_dir, filename)
            shutil.move(file_path, new_path)
            
            await self.notification.notify(
                f"Processed TV show: {show_info['name']} S{season:02d}E{episode:02d}",
                level="info"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing TV show {file_path}: {e}")
            await self.notification.notify(
                f"Error processing TV show {filename}: {str(e)}",
                level="error"
            )
            await self.move_to_unmatched(file_path)
            return False
            
    async def move_to_unmatched(self, file_path: str) -> None:
        """Move file to unmatched directory."""
        try:
            unmatched_dir = self.config_manager["paths"]["unmatched_dir"]
            os.makedirs(unmatched_dir, exist_ok=True)
            
            new_path = os.path.join(unmatched_dir, os.path.basename(file_path))
            shutil.move(file_path, new_path)
            
            await self.notification.notify(
                f"Moved to unmatched: {os.path.basename(file_path)}",
                level="info"
            )
            
        except Exception as e:
            self.logger.error(f"Error moving file to unmatched: {e}")
            await self.notification.notify(
                f"Error moving to unmatched: {str(e)}",
                level="error"
            )