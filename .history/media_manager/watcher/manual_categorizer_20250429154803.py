"""Manual categorization handler for unmatched media files."""
import os
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from common.notification_service import NotificationService
from watcher.categorizer import MediaCategorizer

class ManualCategorizer:
    """Handles manual categorization of media files."""
    
    def __init__(self, config: Dict[str, Any], notification_service: NotificationService, 
                 media_categorizer: MediaCategorizer):
        """
        Initialize manual categorizer.
        
        Args:
            config: Application configuration
            notification_service: Notification service instance
            media_categorizer: Media categorizer instance
        """
        self.config = config
        self.notification = notification_service
        self.categorizer = media_categorizer
        self.logger = logging.getLogger("ManualCategorizer")
        
        # Track active categorization sessions
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._session_lock = asyncio.Lock()
        
        # Register commands
        self._register_commands()
        
    def _register_commands(self) -> None:
        """Register command handlers."""
        asyncio.create_task(self.notification.register_command("categorize", self._handle_categorize))
        asyncio.create_task(self.notification.register_command("skip", self._handle_skip))
        asyncio.create_task(self.notification.register_command("list", self._handle_list))
        
    async def _handle_categorize(self, message: Any) -> None:
        """Handle /categorize command."""
        unmatched_files = self._get_unmatched_files()
        
        if not unmatched_files:
            await self.notification.notify(
                "✅ No Files Need Categorization!\n\n"
                "All files have been processed and organized.\n"
                "Send me new files to download and categorize.",
                level="info"
            )
            return
            
        # Get next file to categorize
        file_path = unmatched_files[0]
        await self._start_categorization(file_path)

    async def _start_categorization(self, file_path: str) -> None:
        """Start categorization session for a file."""
        filename = os.path.basename(file_path)
        
        # First, display file info and options
        await self.notification.notify(
            f"📂 Manual Categorization\n\n"
            f"File: {filename}\n\n"
            f"Please select the content type:\n"
            f"1️⃣ Movie\n"
            f"2️⃣ TV Show\n\n"
            f"Reply with 1 for Movie or 2 for TV Show\n"
            f"Or use /skip to skip this file",
            level="info"
        )

    async def _handle_type_response(self, file_path: str, response: str) -> None:
        """Handle content type response."""
        filename = os.path.basename(file_path)
        
        if response == "1":  # Movie
            await self.notification.notify(
                f"🎬 Movie Selected: {filename}\n\n"
                f"Please provide the movie information in this format:\n"
                f"Title (Year)\n\n"
                f"Examples:\n"
                f"• The Matrix (1999)\n"
                f"• Inception (2010)",
                level="info"
            )
            
        elif response == "2":  # TV Show
            await self.notification.notify(
                f"📺 TV Show Selected: {filename}\n\n"
                f"Please provide the show information in this format:\n"
                f"Show Name | Season | Episode\n\n"
                f"Examples:\n"
                f"• Breaking Bad | 1 | 5\n"
                f"• The Office | 3 | 12",
                level="info"
            )
        else:
            await self.notification.notify(
                f"❌ Invalid Selection\n\n"
                f"Please reply with:\n"
                f"1️⃣ for Movie\n"
                f"2️⃣ for TV Show\n\n"
                f"Or use /skip to skip this file",
                level="warning"
            )

    async def _process_movie_input(self, file_path: str, title: str, year: str) -> None:
        """Process movie information input."""
        try:
            # Search TMDB
            movie_info = await self.categorizer.tmdb.search_movie(title, year)
            if not movie_info:
                await self.notification.notify(
                    f"❌ Movie Not Found\n\n"
                    f"Could not find: {title} ({year})\n\n"
                    f"SUGGESTIONS:\n"
                    f"1️⃣ Check the spelling\n"
                    f"2️⃣ Try alternative titles\n"
                    f"3️⃣ Verify the release year\n\n"
                    f"Please try again with correct information",
                    level="warning"
                )
                return

            # Show movie details for confirmation
            await self.notification.notify(
                f"🎬 Movie Found!\n\n"
                f"Title: {movie_info['title']}\n"
                f"Year: {movie_info['release_date'][:4]}\n"
                f"Rating: {movie_info.get('vote_average', 'N/A')}/10\n"
                f"Overview: {movie_info.get('overview', 'No overview available.')[:200]}...\n\n"
                f"Is this correct? Reply with:\n"
                f"👍 YES - to confirm and move the file\n"
                f"👎 NO - to try again with different info",
                level="info"
            )

        except Exception as e:
            await self.notification.notify(
                f"❌ Error Processing Movie\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or use /skip to skip this file",
                level="error"
            )

    async def _process_tv_show_input(self, file_path: str, show: str, season: int, episode: int) -> None:
        """Process TV show information input."""
        try:
            # Search TMDB
            show_info = await self.categorizer.tmdb.search_tv_show(show)
            if not show_info:
                await self.notification.notify(
                    f"❌ TV Show Not Found\n\n"
                    f"Could not find: {show}\n\n"
                    f"SUGGESTIONS:\n"
                    f"1️⃣ Check the spelling\n"
                    f"2️⃣ Try alternative titles\n"
                    f"3️⃣ Use the official show name\n\n"
                    f"Please try again with correct information",
                    level="warning"
                )
                return

            # Show TV show details for confirmation
            await self.notification.notify(
                f"📺 TV Show Found!\n\n"
                f"Show: {show_info['name']}\n"
                f"First Aired: {show_info.get('first_air_date', 'Unknown')[:4]}\n"
                f"Season: {season}\n"
                f"Episode: {episode}\n"
                f"Rating: {show_info.get('vote_average', 'N/A')}/10\n"
                f"Overview: {show_info.get('overview', 'No overview available.')[:200]}...\n\n"
                f"Is this correct? Reply with:\n"
                f"👍 YES - to confirm and move the file\n"
                f"👎 NO - to try again with different info",
                level="info"
            )

        except Exception as e:
            await self.notification.notify(
                f"❌ Error Processing TV Show\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or use /skip to skip this file",
                level="error"
            )

    async def _handle_skip(self, message: Any) -> None:
        """Handle /skip command."""
        unmatched_files = self._get_unmatched_files()
        if not unmatched_files:
            await self.notification.notify(
                "✅ No Files Need Categorization!\n\n"
                "All files have been processed and organized.",
                level="info"
            )
            return

        current_file = unmatched_files[0]
        filename = os.path.basename(current_file)
        
        # Skip current file
        await self.notification.notify(
            f"⏭️ Skipped: {filename}\n\n"
            f"The file will remain in the unmatched folder.\n"
            f"Use /categorize to try again later.",
            level="info"
        )
        
        # Move to next file if available
        if len(unmatched_files) > 1:
            await self._start_categorization(unmatched_files[1])

    async def _handle_list(self, message: Any) -> None:
        """Handle /list command."""
        unmatched_files = self._get_unmatched_files()
        
        if not unmatched_files:
            await self.notification.notify(
                "✅ No Unmatched Files!\n\n"
                "All files have been processed and organized.",
                level="info"
            )
            return
            
        # Format list with numbers and file sizes
        file_list = []
        for i, file_path in enumerate(unmatched_files, 1):
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path)
            size_str = self._format_size(size)
            file_list.append(f"{i}. {filename} ({size_str})")

        await self.notification.notify(
            f"📋 Unmatched Files ({len(unmatched_files)}):\n\n"
            f"{chr(10).join(file_list)}\n\n"
            f"Use /categorize to process these files\n"
            f"Or use /skip to skip the current file",
            level="info"
        )

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"