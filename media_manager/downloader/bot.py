"""Telegram downloader module."""
import os
import asyncio
import logging
from typing import Dict, Any, Optional, Set
from telethon import TelegramClient, events
from telethon.tl.types import Message, Document, DocumentAttributeVideo
from media_manager.common.notification_service import NotificationService

class TelegramDownloader:
    """Handles Telegram media downloads."""

    def __init__(self, config_manager, notification_service: NotificationService):
        """Initialize the downloader."""
        self.config = config_manager.config
        self.logger = logging.getLogger("TelegramDownloader")
        self.notification = notification_service
        
        # Get Telegram credentials
        self.api_id = self.config["telegram"]["api_id"]
        self.api_hash = self.config["telegram"]["api_hash"]
        self.bot_token = self.config["telegram"]["bot_token"]
        self.download_dir = self.config["paths"]["telegram_download_dir"]
        self.temp_dir = self.config["paths"]["temp_download_dir"]
        
        # Ensure directories exist
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Initialize client with bot token
        session_file = os.path.join('/app/.sessions', 'media_downloader')
        self.client = TelegramClient(
            session_file,
            self.api_id,
            self.api_hash
        )

        # Track downloads
        self._active_downloads: Set[asyncio.Task] = set()
        self._stopping = False

    async def start(self) -> None:
        """Start the downloader."""
        try:
            # Start the client with bot token
            await self.client.start(bot_token=self.bot_token)
            
            # Verify connection
            if not await self.client.is_user_authorized():
                raise Exception("Failed to authenticate with Telegram")
                
            self.logger.info("Telegram client started successfully")
            
            # Register message handler
            @self.client.on(events.NewMessage())
            async def handle_new_message(event: Message):
                if event.media and not self._stopping:
                    await self._process_media(event)
            
            await self.notification.ensure_token_and_notify(
                "TelegramDownloader",
                "Media downloader started successfully.\n"
                f"Monitoring for new media in chat: {self.config['telegram']['chat_id']}\n"
                f"Downloads will be saved to: {os.path.abspath(self.download_dir)}",
                level="info"
            )
                    
        except Exception as e:
            self.logger.error(f"Failed to start Telegram client: {e}")
            await self.notification.ensure_token_and_notify(
                "TelegramDownloader",
                f"Failed to start downloader: {str(e)}",
                level="error"
            )
            raise

    async def stop(self) -> None:
        """Stop the downloader."""
        self._stopping = True
        if self._active_downloads:
            await self.notification.ensure_token_and_notify(
                "TelegramDownloader",
                f"Waiting for {len(self._active_downloads)} downloads to complete...",
                level="info"
            )
            await asyncio.gather(*self._active_downloads)
        await self.client.disconnect()
        await self.notification.ensure_token_and_notify(
            "TelegramDownloader",
            "Media downloader stopped",
            level="info"
        )
        self.logger.info("Telegram client stopped")

    async def _process_media(self, event: Message) -> None:
        """Process a media message."""
        try:
            if not isinstance(event.media, Document):
                return

            # Get file attributes
            attributes = event.media.attributes
            video_attr = next((a for a in attributes if isinstance(a, DocumentAttributeVideo)), None)
            if not video_attr:
                return

            # Get file info
            file_name = event.file.name or f"video_{event.id}.mp4"
            file_size = event.file.size
            temp_path = os.path.join(self.temp_dir, file_name)
            final_path = os.path.join(self.download_dir, file_name)

            # Check if file already exists
            if os.path.exists(final_path):
                self.logger.info(f"File already exists: {final_path}")
                await self.notification.ensure_token_and_notify(
                    "TelegramDownloader",
                    f"⚠️ File already exists: {file_name}",
                    level="warning",
                    file_path=final_path
                )
                return

            # Acquire token for initial notification
            await self.notification.ensure_token_and_notify(
                "TelegramDownloader",
                f"📥 Starting Download:\n"
                f"File: {file_name}\n"
                f"Size: {file_size / 1024 / 1024:.2f} MB\n"
                f"Downloading to: {os.path.relpath(temp_path, start=self.temp_dir)}",
                level="info",
                file_path=temp_path
            )

            # Start download
            download_task = asyncio.create_task(self._download_file(event, temp_path, final_path))
            self._active_downloads.add(download_task)
            download_task.add_done_callback(self._active_downloads.discard)

        except Exception as e:
            self.logger.error(f"Error processing media message: {e}")
            await self.notification.ensure_token_and_notify(
                "TelegramDownloader",
                f"Error processing media: {str(e)}",
                level="error"
            )

    async def _download_file(self, event: Message, temp_path: str, final_path: str) -> None:
        """Download a file from Telegram."""
        try:
            # Track progress for notifications
            last_progress = -1
            last_notification_time = 0
            start_time = asyncio.get_event_loop().time()
            file_size = event.file.size

            async def progress_callback(received_bytes, total):
                nonlocal last_progress, last_notification_time
                current_time = asyncio.get_event_loop().time()
                progress = int((received_bytes / total) * 100)
                
                # Update progress every 5% or every 30 seconds, whichever comes first
                if (progress >= last_progress + 5) or (current_time - last_notification_time >= 30):
                    speed = received_bytes / (current_time - start_time) / 1024 / 1024  # MB/s
                    remaining_bytes = total - received_bytes
                    eta_seconds = remaining_bytes / (speed * 1024 * 1024) if speed > 0 else 0
                    
                    await self.notification.ensure_token_and_notify(
                        "TelegramDownloader",
                        f"📥 Downloading: {event.file.name}\n"
                        f"Progress: {progress}%\n"
                        f"Speed: {speed:.2f} MB/s\n"
                        f"ETA: {int(eta_seconds/60)}m {int(eta_seconds%60)}s",
                        level="progress",
                        file_path=temp_path
                    )
                    last_progress = progress
                    last_notification_time = current_time

            # Download to temp directory first
            await event.download_media(
                file=temp_path,
                progress_callback=progress_callback
            )

            # Move to final location
            os.rename(temp_path, final_path)

            # Final notification
            download_time = asyncio.get_event_loop().time() - start_time
            avg_speed = file_size / download_time / 1024 / 1024
            
            await self.notification.ensure_token_and_notify(
                "TelegramDownloader",
                f"✅ Download Complete!\n\n"
                f"📁 File: {event.file.name}\n"
                f"📊 Size: {file_size / 1024 / 1024:.2f} MB\n"
                f"⚡ Avg Speed: {avg_speed:.2f} MB/s\n"
                f"⏱️ Time: {download_time:.1f}s\n\n"
                f"The file will be processed by the Media Categorizer shortly.",
                level="success",
                file_path=final_path
            )

            # Release token to let categorizer take over
            self.notification.release_token("TelegramDownloader")

        except Exception as e:
            self.logger.error(f"Error downloading {event.file.name}: {e}")
            await self.notification.ensure_token_and_notify(
                "TelegramDownloader",
                f"❌ Download Failed!\n\n"
                f"File: {event.file.name}\n"
                f"Error: {str(e)}",
                level="error",
                file_path=temp_path
            )
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)