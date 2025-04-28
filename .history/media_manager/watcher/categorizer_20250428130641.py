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
        
        # Compile regex patterns
        self.movie_patterns = [
            r'^(?P<title>.+?)[\. ](?P<year>19\d{2}|20\d{2})',
            r'^(?P<title>.+?)[\. ]\((?P<year>19\d{2}|20\d{2})\)'
        ]
        self.tv_patterns = [
            r'^(?P<show>.+?)[\. ]S(?P<season>\d{1,2})E(?P<episode>\d{1,2})',
            r'^(?P<show>.+?)[\. ](?P<season>\d{1,2})x(?P<episode>\d{1,2})'
        ]
        
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
            
            # Try automatic categorization
            media_type, info = self._parse_filename(filename)
            
            if not media_type or not info:
                # Request manual categorization
                await self.notification.notify(
                    f"Unable to automatically categorize: {filename}\n"
                    "Please use /categorize to process manually.",
                    level="warning"
                )
                return False
                
            # Process based on media type
            if media_type == "movie":
                success = await self._process_movie(file_path, info)
            else:  # TV Show
                success = await self._process_tv_show(file_path, info)
                
            if success:
                await self.notification.notify(
                    f"Successfully processed: {filename}",
                    level="success"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            await self.notification.notify(
                f"Error processing file: {str(e)}",
                level="error"
            )
            return False
            
    def _parse_filename(self, filename: str) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
        """Parse filename to extract media information."""
        # Try movie patterns
        for pattern in self.movie_patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                groups = match.groupdict()
                # Clean up title by replacing dots with spaces and stripping
                groups["title"] = groups["title"].replace(".", " ").strip()
                return "movie", groups
                
        # Try TV show patterns
        for pattern in self.tv_patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                groups = match.groupdict()
                # Clean up show name by replacing dots with spaces and stripping
                groups["show"] = groups["show"].replace(".", " ").strip()
                return "tv", groups
                
        return None, None
        
    async def _process_movie(self, file_path: str, info: Dict[str, str]) -> bool:
        """Process a movie file."""
        try:
            # Get movie details from TMDB
            movie_info = await self.tmdb.search_movie(
                info["title"],
                year=int(info["year"])
            )
            
            if not movie_info:
                await self.notification.notify(
                    f"Could not find movie info for: {info['title']} ({info['year']})",
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
            new_path = os.path.join(movie_dir, os.path.basename(file_path))
            shutil.move(file_path, new_path)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing movie {file_path}: {e}")
            return False
            
    async def _process_tv_show(self, file_path: str, info: Dict[str, str]) -> bool:
        """Process a TV show episode."""
        try:
            # Get show details from TMDB
            show_info = await self.tmdb.search_tv_show(info["show"])
            
            if not show_info:
                await self.notification.notify(
                    f"Could not find TV show info for: {info['show']}",
                    level="warning"
                )
                return False
                
            # Create destination path
            tv_dir = self.config["paths"]["tv_shows_dir"]
            show_dir = os.path.join(tv_dir, show_info["name"])
            season_dir = os.path.join(show_dir, f"Season {int(info['season']):02d}")
            os.makedirs(season_dir, exist_ok=True)
            
            # Move file
            new_path = os.path.join(season_dir, os.path.basename(file_path))
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