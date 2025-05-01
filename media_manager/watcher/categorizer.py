"""File categorization and processing module."""
import os
import re
import shutil
import logging
import time
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
        self.config = config_manager.config  # Store config for easier access
        
        # Validate TMDB API key
        tmdb_config = self.config_manager.get("tmdb", {})
        tmdb_api_key = tmdb_config.get("api_key")
        if not tmdb_api_key or tmdb_api_key == "${TMDB_API_KEY}":
            self.logger.error("TMDB API key not configured")
            self.tmdb = None
        else:
            self.tmdb = TMDBClient(tmdb_api_key)
            self.logger.info("TMDB client initialized successfully")

    async def process_file(self, filepath: str) -> None:
        """Process a media file through the categorization workflow."""
        try:
            filename = os.path.basename(filepath)
            start_time = time.time()
            
            # Initial notification
            if self.notification:
                await self.notification.notify(
                    f"ℹ️ 📝 Started processing: {filename}"
                )
            
            # Analysis stage
            if self.notification:
                await self.notification.notify(
                    f"🔄 Stage: Analyzing {filename}"
                )
            metadata = await self._analyze_file(filepath)
            
            # TMDb verification stage
            if self.notification:
                await self.notification.notify(
                    f"🔄 Stage: Verifying with TMDb"
                )
            verified_metadata = await self._verify_with_tmdb(metadata)
            
            # File moving stage
            if self.notification:
                await self.notification.notify(
                    f"🔄 Stage: Moving to library"
                )
            new_path = await self._move_to_library(filepath, verified_metadata)
            
            # Process timing
            elapsed = time.time() - start_time
            
            # Success notification
            if self.notification:
                await self.notification.notify(
                    f"✅ Processed {filename} in {elapsed:.1f} s\n"
                    f"Moved to: {new_path}"
                )
                
        except Exception as e:
            if self.notification:
                await self.notification.notify(
                    f"❌ Error processing {filename}: {str(e)}",
                    level="error"
                )
            raise

    async def _analyze_file(self, filepath: str) -> dict:
        """Analyze the media file to extract metadata."""
        filename = os.path.basename(filepath)
        metadata = {"original_path": filepath}
        
        # Try parsing as movie first
        title, year = self.parse_movie_filename(filename)
        if title and year:
            metadata.update({
                "type": "movie",
                "title": title,
                "year": year
            })
            return metadata
            
        # Try parsing as TV show
        show, season, episode = self.parse_tv_show_filename(filename)
        if all([show, season, episode]):
            metadata.update({
                "type": "tv",
                "show_name": show,
                "season": season,
                "episode": episode
            })
            return metadata
            
        raise ValueError(f"Could not parse filename: {filename}")

    async def _verify_with_tmdb(self, metadata: dict) -> dict:
        """Verify and enhance metadata using TMDb API."""
        if not self.tmdb:
            raise RuntimeError("TMDB client not initialized")
            
        if metadata["type"] == "movie":
            movie_info = await self.tmdb.search_movie(
                metadata["title"], 
                metadata["year"]
            )
            if not movie_info:
                raise ValueError(f"No TMDB match found for movie: {metadata['title']} ({metadata['year']})")
            metadata.update(movie_info)
            
        else:  # TV show
            show_info = await self.tmdb.search_tv_show(metadata["show_name"])
            if not show_info:
                raise ValueError(f"No TMDB match found for TV show: {metadata['show_name']}")
            metadata.update(show_info)
            
        return metadata

    async def _move_to_library(self, filepath: str, metadata: dict) -> str:
        """Move the file to the appropriate library location."""
        filename = os.path.basename(filepath)
        
        if metadata["type"] == "movie":
            dest_dir = os.path.join(
                self.config["paths"]["movies_dir"],
                f"{metadata['title']} ({metadata['release_date'][:4]})"
            )
        else:
            dest_dir = os.path.join(
                self.config["paths"]["tv_shows_dir"],
                metadata["name"],
                f"Season {metadata['season']:02d}"
            )
            
        os.makedirs(dest_dir, exist_ok=True)
        new_path = os.path.join(dest_dir, filename)
        shutil.move(filepath, new_path)
        
        return new_path

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
        
    async def process_movie(self, file_path: str) -> bool:
        """Process a movie file."""
        filename = os.path.basename(file_path)
        try:
            title, year = self.parse_movie_filename(filename)
            if not title or not year:
                return False

            # Search TMDB
            movie_info = await self.tmdb.search_movie(title, year)
            if not movie_info:
                await self.notification.ensure_token_and_notify(
                    "MediaCategorizer",
                    f"🔍 No TMDB Match Found:\n"
                    f"Title: {title}\n"
                    f"Year: {year}\n\n"
                    f"SUGGESTIONS:\n"
                    f"1️⃣ Check if the title is correct\n"
                    f"2️⃣ Verify the release year\n"
                    f"3️⃣ Use /categorize for manual matching",
                    level="warning",
                    file_path=file_path
                )
                return await self.move_to_unmatched(file_path)

            # Create movie directory
            paths_config = self.config_manager.get("paths", {})
            movies_dir = paths_config.get("movies_dir", "media/movies")
            movie_dir = os.path.join(
                movies_dir,
                f"{movie_info['title']} ({movie_info['release_date'][:4]})"
            )
            os.makedirs(movie_dir, exist_ok=True)

            # Move file
            new_path = os.path.join(movie_dir, filename)
            await self.notification.ensure_token_and_notify(
                "MediaCategorizer",
                f"📦 Moving Movie File:\n"
                f"Title: {movie_info['title']} ({movie_info['release_date'][:4]})\n"
                f"Rating: {movie_info.get('vote_average', 'N/A')}/10\n"
                f"To: {os.path.relpath(movie_dir, movies_dir)}",
                level="info",
                file_path=new_path
            )
            shutil.move(file_path, new_path)
            
            await self.notification.ensure_token_and_notify(
                "MediaCategorizer",
                f"✅ Movie Processed Successfully!\n\n"
                f"🎬 {movie_info['title']} ({movie_info['release_date'][:4]})\n"
                f"⭐ Rating: {movie_info.get('vote_average', 'N/A')}/10\n"
                f"📝 Overview: {movie_info.get('overview', 'No overview available.')[:150]}...\n\n"
                f"The movie will appear in Jellyfin shortly.",
                level="success",
                file_path=new_path
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing movie {file_path}: {e}")
            await self.notification.ensure_token_and_notify(
                "MediaCategorizer",
                f"❌ Movie Processing Failed:\n"
                f"File: {filename}\n"
                f"Error: {str(e)}\n\n"
                f"SUGGESTIONS:\n"
                f"1️⃣ Check internet connection\n"
                f"2️⃣ Verify TMDB API key\n"
                f"3️⃣ Try manual categorization with /categorize",
                level="error",
                file_path=file_path
            )
            return False

    async def process_tv_show(self, file_path: str) -> bool:
        """Process a TV show episode."""
        filename = os.path.basename(file_path)
        try:
            show, season, episode = self.parse_tv_show_filename(filename)
            if not all([show, season, episode]):
                return False

            # Search TMDB
            show_info = await self.tmdb.search_tv_show(show)
            if not show_info:
                await self.notification.ensure_token_and_notify(
                    "MediaCategorizer",
                    f"🔍 No TMDB Match Found:\n"
                    f"Show: {show}\n"
                    f"Season: {season}\n"
                    f"Episode: {episode}\n\n"
                    f"SUGGESTIONS:\n"
                    f"1️⃣ Check if the show name is correct\n"
                    f"2️⃣ Try alternative title variations\n"
                    f"3️⃣ Use /categorize for manual matching",
                    level="warning",
                    file_path=file_path
                )
                return await self.move_to_unmatched(file_path)

            # Create show/season directories
            paths_config = self.config_manager.get("paths", {})
            tv_shows_dir = paths_config.get("tv_shows_dir", "media/tv_shows")
            show_dir = os.path.join(
                tv_shows_dir,
                show_info['name']
            )
            season_dir = os.path.join(show_dir, f"Season {season:02d}")
            os.makedirs(season_dir, exist_ok=True)

            # Move file
            new_path = os.path.join(season_dir, filename)
            await self.notification.ensure_token_and_notify(
                "MediaCategorizer",
                f"📦 Moving TV Episode:\n"
                f"Show: {show_info['name']}\n"
                f"Season: {season:02d}\n"
                f"Episode: {episode:02d}\n"
                f"Rating: {show_info.get('vote_average', 'N/A')}/10\n"
                f"To: {os.path.relpath(season_dir, tv_shows_dir)}",
                level="info",
                file_path=new_path
            )
            shutil.move(file_path, new_path)

            await self.notification.ensure_token_and_notify(
                "MediaCategorizer",
                f"✅ TV Episode Processed Successfully!\n\n"
                f"📺 {show_info['name']}\n"
                f"🔢 Season {season:02d}, Episode {episode:02d}\n"
                f"⭐ Show Rating: {show_info.get('vote_average', 'N/A')}/10\n"
                f"📝 Overview: {show_info.get('overview', 'No overview available.')[:150]}...\n\n"
                f"The episode will appear in Jellyfin shortly.",
                level="success",
                file_path=new_path
            )
            return True

        except Exception as e:
            self.logger.error(f"Error processing TV show {file_path}: {e}")
            await self.notification.ensure_token_and_notify(
                "MediaCategorizer",
                f"❌ TV Show Processing Failed:\n"
                f"File: {filename}\n"
                f"Error: {str(e)}\n\n"
                f"SUGGESTIONS:\n"
                f"1️⃣ Check internet connection\n"
                f"2️⃣ Verify TMDB API key\n"
                f"3️⃣ Try manual categorization with /categorize",
                level="error",
                file_path=file_path
            )
            return False

    async def move_to_unmatched(self, file_path: str) -> bool:
        """Move file to unmatched directory."""
        unmatched_dir = self.config["paths"]["unmatched_dir"]
        dest_path = os.path.join(unmatched_dir, os.path.basename(file_path))
        
        try:
            os.makedirs(unmatched_dir, exist_ok=True)
            shutil.move(file_path, dest_path)
            await self.notification.ensure_token_and_notify(
                "MediaCategorizer",
                "Moved to unmatched directory",
                level="warning",
                file_path=dest_path
            )
            return True
        except OSError as e:
            self.logger.error(f"Failed to move file to unmatched dir: {e}")
            await self.notification.ensure_token_and_notify(
                "MediaCategorizer",
                f"Error moving file to unmatched directory: {str(e)}",
                level="error",
                file_path=file_path
            )
            return False

    def get_final_path(self, media_info: Dict[str, Any]) -> str:
        """Get the final path where the file will be/was moved."""
        if media_info["type"] == "movie":
            return os.path.join(
                self.config["paths"]["movies_dir"],
                f"{media_info['title']} ({media_info['year']})"
            )
        else:
            return os.path.join(
                self.config["paths"]["tv_shows_dir"],
                media_info["series_name"],
                f"Season {media_info['season']:02d}"
            )