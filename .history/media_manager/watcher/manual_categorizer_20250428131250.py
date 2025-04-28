"""Manual categorization handler for unmatched media files."""
import os
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from media_manager.common.notification_service import NotificationService
from media_manager.watcher.categorizer import MediaCategorizer

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
        try:
            unmatched = self._get_unmatched_files()
            if not unmatched:
                await self.notification.notify(
                    "No files need categorization",
                    level="info"
                )
                return
                
            # Start categorization session for first file
            await self._start_categorization(unmatched[0])
                
        except Exception as e:
            self.logger.error(f"Error handling categorize command: {e}")
            await self.notification.notify(
                f"Error starting categorization: {str(e)}",
                level="error"
            )
            
    async def _handle_skip(self, message: Any) -> None:
        """Handle /skip command."""
        try:
            async with self._session_lock:
                if not self._active_sessions:
                    await self.notification.notify(
                        "No active categorization session",
                        level="warning"
                    )
                    return
                    
                # Get next file
                unmatched = self._get_unmatched_files()
                if not unmatched:
                    await self.notification.notify(
                        "No more files to categorize",
                        level="info"
                    )
                    return
                    
                # Start new session
                await self._start_categorization(unmatched[0])
                
        except Exception as e:
            self.logger.error(f"Error handling skip command: {e}")
            await self.notification.notify(
                f"Error skipping file: {str(e)}",
                level="error"
            )
            
    async def _handle_list(self, message: Any) -> None:
        """Handle /list command."""
        try:
            unmatched = self._get_unmatched_files()
            if not unmatched:
                await self.notification.notify(
                    "No files need categorization",
                    level="info"
                )
                return
                
            # Format list message
            files_text = "\n".join(
                f"{i+1}. {os.path.basename(f)}" 
                for i, f in enumerate(unmatched[:10])
            )
            
            remaining = len(unmatched) - 10 if len(unmatched) > 10 else 0
            if remaining > 0:
                files_text += f"\n\n...and {remaining} more files"
                
            await self.notification.notify(
                f"Files needing categorization:\n\n{files_text}",
                level="info"
            )
            
        except Exception as e:
            self.logger.error(f"Error handling list command: {e}")
            await self.notification.notify(
                f"Error listing files: {str(e)}",
                level="error"
            )
            
    def _get_unmatched_files(self) -> List[str]:
        """Get list of files needing categorization."""
        unmatched_dir = self.config["paths"]["unmatched_dir"]
        if not os.path.exists(unmatched_dir):
            return []
            
        return [
            os.path.join(unmatched_dir, f)
            for f in os.listdir(unmatched_dir)
            if os.path.isfile(os.path.join(unmatched_dir, f))
        ]
        
    async def _start_categorization(self, file_path: str) -> None:
        """Start categorization session for a file."""
        try:
            filename = os.path.basename(file_path)
            
            # Clear any existing session
            async with self._session_lock:
                self._active_sessions.clear()
                self._active_sessions[file_path] = {
                    "stage": "type",
                    "metadata": {}
                }
            
            # Ask for media type
            prompt = (
                f"Categorizing: {filename}\n\n"
                "What type of media is this?\n"
                "1. Movie\n"
                "2. TV Show\n\n"
                "Reply with number or /skip to skip"
            )
            
            response = await self.notification.wait_for_response(prompt)
            if not response:
                return
                
            await self._handle_type_response(file_path, response)
            
        except Exception as e:
            self.logger.error(f"Error starting categorization: {e}")
            await self.notification.notify(
                f"Error starting categorization: {str(e)}",
                level="error"
            )
            
    async def _handle_type_response(self, file_path: str, response: str) -> None:
        """Handle media type response."""
        try:
            media_type = None
            if response == "1":
                media_type = "movie"
            elif response == "2":
                media_type = "tv"
            else:
                await self.notification.notify(
                    "Invalid selection. Please try again.",
                    level="warning"
                )
                await self._start_categorization(file_path)
                return
                
            # Update session
            async with self._session_lock:
                if file_path in self._active_sessions:
                    self._active_sessions[file_path]["metadata"]["type"] = media_type
                    self._active_sessions[file_path]["stage"] = "details"
                    
            # Get additional details based on type
            if media_type == "movie":
                await self._get_movie_details(file_path)
            else:
                await self._get_tv_show_details(file_path)
                
        except Exception as e:
            self.logger.error(f"Error handling type response: {e}")
            await self.notification.notify(
                f"Error processing response: {str(e)}",
                level="error"
            )
            
    async def _get_movie_details(self, file_path: str) -> None:
        """Get movie details from user."""
        try:
            title = await self.notification.wait_for_response(
                f"Enter movie title for: {os.path.basename(file_path)}\n"
                "(Just the title, no year)"
            )
            
            if not title:
                await self.notification.notify(
                    "Categorization cancelled due to timeout.",
                    level="warning"
                )
                async with self._session_lock:
                    self._active_sessions.pop(file_path, None)
                return

            year = await self.notification.wait_for_response(
                "Enter the movie's release year:"
            )
            
            if not year:
                await self.notification.notify(
                    "Categorization cancelled due to timeout.",
                    level="warning"
                )
                async with self._session_lock:
                    self._active_sessions.pop(file_path, None)
                return

            # Validate year
            try:
                year_int = int(year.strip())
                if year_int < 1900 or year_int > 2100:
                    raise ValueError("Year must be between 1900 and 2100")
            except ValueError as e:
                await self.notification.notify(
                    f"Invalid year format: {str(e)}",
                    level="warning"
                )
                return

            # Update metadata
            async with self._session_lock:
                if file_path in self._active_sessions:
                    self._active_sessions[file_path]["metadata"].update({
                        "title": title.strip(),
                        "year": year_int
                    })
                    
            # Process file with new metadata
            await self._process_file(file_path)
            
        except Exception as e:
            self.logger.error(f"Error getting movie details: {e}")
            await self.notification.notify(
                f"Error getting movie details: {str(e)}",
                level="error"
            )
            async with self._session_lock:
                self._active_sessions.pop(file_path, None)
            
    async def _get_tv_show_details(self, file_path: str) -> None:
        """Get TV show details from user."""
        try:
            filename = os.path.basename(file_path)
            
            # Ask for show title
            title_prompt = (
                f"Enter TV show title for: {filename}\n"
                "(Just the title, no season/episode)"
            )
            
            title = await self.notification.wait_for_response(title_prompt)
            if not title:
                await self.notification.notify(
                    "Categorization cancelled due to timeout.",
                    level="warning"
                )
                async with self._session_lock:
                    self._active_sessions.pop(file_path, None)
                return
                
            # Ask for season number
            season_prompt = "Enter season number:"
            season = await self.notification.wait_for_response(season_prompt)
            if not season:
                await self.notification.notify(
                    "Categorization cancelled due to timeout.",
                    level="warning"
                )
                async with self._session_lock:
                    self._active_sessions.pop(file_path, None)
                return
                
            try:
                season_int = int(season)
                if season_int < 1:
                    raise ValueError()
            except ValueError:
                await self.notification.notify(
                    "Invalid season number. Please try again.",
                    level="warning"
                )
                await self._get_tv_show_details(file_path)
                return
                
            # Ask for episode number
            episode_prompt = "Enter episode number:"
            episode = await self.notification.wait_for_response(episode_prompt)
            if not episode:
                await self.notification.notify(
                    "Categorization cancelled due to timeout.",
                    level="warning"
                )
                async with self._session_lock:
                    self._active_sessions.pop(file_path, None)
                return
                
            try:
                episode_int = int(episode)
                if episode_int < 1:
                    raise ValueError()
            except ValueError:
                await self.notification.notify(
                    "Invalid episode number. Please try again.",
                    level="warning"
                )
                await self._get_tv_show_details(file_path)
                return
                
            # Update metadata
            async with self._session_lock:
                if file_path in self._active_sessions:
                    self._active_sessions[file_path]["metadata"].update({
                        "show": title.strip(),
                        "season": season_int,
                        "episode": episode_int
                    })
                    
            # Process file with new metadata
            await self._process_file(file_path)
            
        except Exception as e:
            self.logger.error(f"Error getting TV show details: {e}")
            await self.notification.notify(
                f"Error getting TV show details: {str(e)}",
                level="error"
            )
            async with self._session_lock:
                self._active_sessions.pop(file_path, None)
            
    async def _process_file(self, file_path: str) -> None:
        """Process file with collected metadata."""
        try:
            # Get metadata from session
            metadata = None
            async with self._session_lock:
                if file_path in self._active_sessions:
                    metadata = self._active_sessions[file_path]["metadata"]
                    
            if not metadata:
                await self.notification.notify(
                    "Error: No metadata available",
                    level="error"
                )
                return
                
            # Process based on type
            success = False
            if metadata["type"] == "movie":
                success = await self.categorizer._process_movie(file_path, metadata)
            else:
                success = await self.categorizer._process_tv_show(file_path, metadata)
                
            if success:
                await self.notification.notify(
                    f"Successfully categorized: {os.path.basename(file_path)}",
                    level="success"
                )
                
                # Clear session
                async with self._session_lock:
                    self._active_sessions.pop(file_path, None)
                    
                # Check for more files
                unmatched = self._get_unmatched_files()
                if unmatched:
                    await self.notification.notify(
                        f"{len(unmatched)} files remaining to categorize",
                        level="info"
                    )
                else:
                    await self.notification.notify(
                        "All files have been categorized!",
                        level="success"
                    )
            else:
                await self.notification.notify(
                    f"Failed to categorize: {os.path.basename(file_path)}",
                    level="error"
                )
                
        except Exception as e:
            self.logger.error(f"Error processing file: {e}")
            await self.notification.notify(
                f"Error processing file: {str(e)}",
                level="error"
            )