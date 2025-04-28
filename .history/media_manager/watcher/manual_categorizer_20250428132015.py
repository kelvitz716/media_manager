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
        # Initialize session first
        async with self._session_lock:
            self._active_sessions[file_path] = {
                "metadata": {},
                "last_activity": time.time()
            }
            
        await self.notification.notify(
            f"Starting categorization for: {os.path.basename(file_path)}\n\n"
            "Please select media type:\n"
            "1. Movie\n"
            "2. TV Show\n\n"
            "Reply with number (1-2)",
            level="info"
        )