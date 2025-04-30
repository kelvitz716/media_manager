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
                    "🚫 Media categorization disabled: TMDB API key not configured\n"
                    "Please configure your TMDB API key in config.json",
                    level="error"
                )
                return False

            filename = os.path.basename(file_path)
            await self.notification.notify(
                f"🔎 Analyzing file: {filename}\n"
                "Checking file format and searching TMDB...",
                level="info"
            )
            
            # Verify file exists and is readable
            if not os.path.exists(file_path):
                self.logger.error(f"File does not exist: {file_path}")
                await self.notification.notify(
                    f"❌ Error: File not found\n"
                    f"File: {filename}\n"
                    f"This could be due to:\n"
                    f"• File was moved or deleted\n"
                    f"• Insufficient permissions",
                    level="error"
                )
                return False
                
            if not os.access(file_path, os.R_OK):
                self.logger.error(f"File is not readable: {file_path}")
                await self.notification.notify(
                    f"❌ Error: Cannot read file\n"
                    f"File: {filename}\n"
                    f"Please check file permissions",
                    level="error"
                )
                return False
            
            # Try as movie first
            title, year = self.parse_movie_filename(filename)
            if title and year:
                self.logger.debug(f"Parsed as movie: {title} ({year})")
                await self.notification.notify(
                    f"🎬 Detected Movie Format:\n"
                    f"Title: {title}\n"
                    f"Year: {year}\n"
                    f"Searching TMDB database...",
                    level="info"
                )
                success = await self.process_movie(file_path)
                if success:
                    return True
                
            # Try as TV show
            show, season, episode = self.parse_tv_show_filename(filename)
            if show and season and episode:
                self.logger.debug(f"Parsed as TV show: {show} S{season:02d}E{episode:02d}")
                await self.notification.notify(
                    f"📺 Detected TV Show Format:\n"
                    f"Show: {show}\n"
                    f"Season: {season}\n"
                    f"Episode: {episode}\n"
                    f"Searching TMDB database...",
                    level="info"
                )
                success = await self.process_tv_show(file_path)
                if success:
                    return True
            
            # Unable to parse
            self.logger.warning(f"Unable to parse filename: {filename}")
            await self.notification.notify(
                f"⚠️ Could Not Categorize:\n"
                f"File: {filename}\n\n"
                f"POSSIBLE REASONS:\n"
                f"1️⃣ Filename format not recognized\n"
                f"2️⃣ Missing year for movies\n"
                f"3️⃣ Incorrect season/episode format\n\n"
                f"Use /categorize to process manually\n"
                f"Or rename the file to match format:\n"
                f"Movies: Title.YEAR.ext or Title (YEAR).ext\n"
                f"TV: Show.Name.S01E02.ext or Show.Name.1x02.ext",
                level="warning"
            )
            await self.move_to_unmatched(file_path)
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
            await self.notification.notify(
                f"❌ Error During Categorization:\n"
                f"File: {filename}\n"
                f"Error: {str(e)}\n\n"
                f"The file has been kept in its original location.\n"
                f"Please try again or use /categorize for manual processing.",
                level="error"
            )
            return False

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
                await self.notification.notify(
                    f"🔍 No TMDB Match Found:\n"
                    f"Title: {title}\n"
                    f"Year: {year}\n\n"
                    f"SUGGESTIONS:\n"
                    f"1️⃣ Check if the title is correct\n"
                    f"2️⃣ Verify the release year\n"
                    f"3️⃣ Use /categorize for manual matching",
                    level="warning"
                )
                await self.move_to_unmatched(file_path)
                return False

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
            await self.notification.notify(
                f"📦 Moving Movie File:\n"
                f"Title: {movie_info['title']} ({movie_info['release_date'][:4]})\n"
                f"Rating: {movie_info.get('vote_average', 'N/A')}/10\n"
                f"To: {os.path.relpath(movie_dir, movies_dir)}",
                level="info"
            )
            shutil.move(file_path, new_path)
            
            await self.notification.notify(
                f"✅ Movie Processed Successfully!\n\n"
                f"🎬 {movie_info['title']} ({movie_info['release_date'][:4]})\n"
                f"⭐ Rating: {movie_info.get('vote_average', 'N/A')}/10\n"
                f"📝 Overview: {movie_info.get('overview', 'No overview available.')[:150]}...\n\n"
                f"The movie will appear in Jellyfin shortly.",
                level="success"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing movie {file_path}: {e}")
            await self.notification.notify(
                f"❌ Movie Processing Failed:\n"
                f"File: {filename}\n"
                f"Error: {str(e)}\n\n"
                f"SUGGESTIONS:\n"
                f"1️⃣ Check internet connection\n"
                f"2️⃣ Verify TMDB API key\n"
                f"3️⃣ Try manual categorization with /categorize",
                level="error"
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
                await self.notification.notify(
                    f"🔍 No TMDB Match Found:\n"
                    f"Show: {show}\n"
                    f"Season: {season}\n"
                    f"Episode: {episode}\n\n"
                    f"SUGGESTIONS:\n"
                    f"1️⃣ Check if the show name is correct\n"
                    f"2️⃣ Try alternative title variations\n"
                    f"3️⃣ Use /categorize for manual matching",
                    level="warning"
                )
                await self.move_to_unmatched(file_path)
                return False

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
            await self.notification.notify(
                f"📦 Moving TV Episode:\n"
                f"Show: {show_info['name']}\n"
                f"Season: {season:02d}\n"
                f"Episode: {episode:02d}\n"
                f"Rating: {show_info.get('vote_average', 'N/A')}/10\n"
                f"To: {os.path.relpath(season_dir, tv_shows_dir)}",
                level="info"
            )
            shutil.move(file_path, new_path)

            await self.notification.notify(
                f"✅ TV Episode Processed Successfully!\n\n"
                f"📺 {show_info['name']}\n"
                f"🔢 Season {season:02d}, Episode {episode:02d}\n"
                f"⭐ Show Rating: {show_info.get('vote_average', 'N/A')}/10\n"
                f"📝 Overview: {show_info.get('overview', 'No overview available.')[:150]}...\n\n"
                f"The episode will appear in Jellyfin shortly.",
                level="success"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error processing TV show {file_path}: {e}")
            await self.notification.notify(
                f"❌ TV Show Processing Failed:\n"
                f"File: {filename}\n"
                f"Error: {str(e)}\n\n"
                f"SUGGESTIONS:\n"
                f"1️⃣ Check internet connection\n"
                f"2️⃣ Verify TMDB API key\n"
                f"3️⃣ Try manual categorization with /categorize",
                level="error"
            )
            return False

    async def move_to_unmatched(self, file_path: str) -> None:
        """Move file to unmatched directory."""
        try:
            filename = os.path.basename(file_path)
            paths_config = self.config_manager.get("paths", {})
            unmatched_dir = paths_config.get("unmatched_dir", "media/unmatched")
            new_path = os.path.join(unmatched_dir, filename)
            
            # Ensure unique filename
            counter = 1
            while os.path.exists(new_path):
                base, ext = os.path.splitext(filename)
                new_path = os.path.join(unmatched_dir, f"{base}_{counter}{ext}")
                counter += 1

            await self.notification.notify(
                f"📁 Moving to Unmatched Folder:\n"
                f"File: {filename}\n"
                f"Use /fw_unmatched to manage unmatched files",
                level="info"
            )
            
            os.makedirs(unmatched_dir, exist_ok=True)
            shutil.move(file_path, new_path)
            
        except Exception as e:
            self.logger.error(f"Error moving file to unmatched: {str(e)}")
            await self.notification.notify(
                f"❌ Error Moving File:\n"
                f"Could not move {filename} to unmatched folder\n"
                f"Error: {str(e)}",
                level="error"
            )
            raise