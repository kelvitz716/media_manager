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
    
    def __init__(self, config: Dict[str, Any], notification_service: NotificationService):
        """
        Initialize categorizer.
        
        Args:
            config: Application configuration
            notification_service: Notification service instance
        """
        self.config = config
        self.logger = logging.getLogger("MediaCategorizer")
        self.notification = notification_service
        self.tmdb = TMDBClient(config["tmdb"]["api_key"])
        
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
        """
        Process and categorize a media file.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            True if file was processed successfully
        """
        try:
            filename = os.path.basename(file_path)
            self.logger.info(f"Processing file: {filename}")
            
            # Try as movie first
            title, year = self.parse_movie_filename(filename)
            if title and year:
                return await self.process_movie(file_path)
                
            # Try as TV show
            show, season, episode = self.parse_tv_show_filename(filename)
            if show and season and episode:
                return await self.process_tv_show(file_path)
                
            # Unable to parse
            await self.notification.notify(
                f"Unable to automatically categorize: {filename}\n"
                "Please use /categorize to process manually.",
                level="warning"
            )
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
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
            
            # Get movie details from TMDB
            movie_info = await self.tmdb.search_movie(title, int(year))
            
            if not movie_info:
                await self.notification.notify(
                    f"Could not find movie info for: {title} ({year})",
                    level="warning"
                )
                return False
                
            # Create destination path
            movies_dir = self.config["paths"]["movies_dir"]
            movie_dir = os.path.join(
                movies_dir,
                f"{movie_info['title']} ({movie_info['year']})"
            )
            os.makedirs(movie_dir, exist_ok=True)
            
            # Move file
            new_path = os.path.join(movie_dir, filename)
            shutil.move(file_path, new_path)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing movie {file_path}: {e}")
            return False
            
    async def process_tv_show(self, file_path: str) -> bool:
        """Process a TV show episode."""
        try:
            filename = os.path.basename(file_path)
            show, season, episode = self.parse_tv_show_filename(filename)
            
            # Get show details from TMDB
            show_info = await self.tmdb.search_tv_show(show)
            
            if not show_info:
                await self.notification.notify(
                    f"Could not find TV show info for: {show}",
                    level="warning"
                )
                return False
                
            # Get episode details
            episode_info = await self.tmdb.get_episode_details(show_info["id"], season, episode)
            if not episode_info:
                await self.notification.notify(
                    f"Could not find episode info for: {show} S{season:02d}E{episode:02d}",
                    level="warning"
                )
                return False
                
            # Create destination path
            tv_dir = self.config["paths"]["tv_shows_dir"]
            show_dir = os.path.join(tv_dir, show_info["name"])
            season_dir = os.path.join(show_dir, f"Season {season:02d}")
            os.makedirs(season_dir, exist_ok=True)
            
            # Move file
            new_path = os.path.join(season_dir, filename)
            shutil.move(file_path, new_path)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing TV show {file_path}: {e}")
            return False
            
    async def move_to_unmatched(self, file_path: str) -> None:
        """Move file to unmatched directory."""
        try:
            unmatched_dir = self.config["paths"]["unmatched_dir"]
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