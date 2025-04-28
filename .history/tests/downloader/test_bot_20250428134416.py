"""Tests for Telegram downloader bot."""
import os
import tempfile
from unittest import IsolatedAsyncioTestCase, mock
from media_manager.common.notification_service import NotificationService
from media_manager.downloader.bot import TelegramDownloader

class TestTelegramDownloader(IsolatedAsyncioTestCase):
    """Test cases for TelegramDownloader."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "paths": {
                "telegram_download_dir": os.path.join(self.temp_dir, "downloads")
            },
            "telegram": {
                "api_id": "test_api_id",
                "api_hash": "test_api_hash",
                "bot_token": "123456:test_bot_token",  # Updated to include colon
                "chat_id": "123456789"
            },
            "download": {
                "chunk_size": 1024,
                "max_retries": 3,
                "retry_delay": 0.1,
                "verify_downloads": True
            }
        }
        self.notification = mock.AsyncMock(spec=NotificationService)
        self.downloader = TelegramDownloader(self.config, self.notification)
        
    async def asyncTearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            
    async def test_process_media_document(self):
        """Test processing media document."""
        # Mock message with document
        message = mock.AsyncMock()
        message.document = mock.AsyncMock()
        message.document.file_id = "test_file_id"
        message.document.file_name = "test.mp4"
        message.document.file_size = 1024
        
        # Mock bot methods
        self.downloader.bot = mock.AsyncMock()
        self.downloader.bot.get_file.return_value = mock.AsyncMock()
        self.downloader.bot.download_file.return_value = [b"test_data"]
        
        # Process media
        await self.downloader._process_media(message)
        
        # Verify file download was attempted
        self.downloader.bot.get_file.assert_called_once_with("test_file_id")
        self.downloader.bot.download_file.assert_called_once()
        
        # Verify notification was sent
        self.notification.notify.assert_called_with(
            "Download complete: test.mp4",
            level="success"
        )
        
    async def test_process_media_video(self):
        """Test processing media video."""
        # Mock message with video
        message = mock.AsyncMock()
        message.video = mock.AsyncMock()
        message.video.file_id = "test_file_id"
        message.video.file_name = "test.mp4"
        message.video.file_size = 1024
        message.document = None
        
        # Mock bot methods
        self.downloader.bot = mock.AsyncMock()
        self.downloader.bot.get_file.return_value = mock.AsyncMock()
        self.downloader.bot.download_file.return_value = [b"test_data"]
        
        # Process media
        await self.downloader._process_media(message)
        
        # Verify file download was attempted
        self.downloader.bot.get_file.assert_called_once_with("test_file_id")
        self.downloader.bot.download_file.assert_called_once()
        
        # Verify notification was sent
        self.notification.notify.assert_called_with(
            "Download complete: test.mp4",
            level="success"
        )
        
    async def test_duplicate_download(self):
        """Test handling duplicate downloads."""
        # Mock message
        message = mock.AsyncMock()
        message.document = mock.AsyncMock()
        message.document.file_id = "test_file_id"
        message.document.file_name = "test.mp4"
        message.document.file_size = 1024
        
        # Add file to active downloads
        self.downloader._active_downloads["test_file_id"] = {
            "filename": "test.mp4",
            "progress": 50
        }
        
        # Mock bot methods
        self.downloader.bot = mock.AsyncMock()
        
        # Try to process same file
        await self.downloader._process_media(message)
        
        # Verify download was not attempted
        self.downloader.bot.get_file.assert_not_called()
        self.downloader.bot.download_file.assert_not_called()
        
        # Verify duplicate message
        message.reply_to.assert_called_with(
            "This file is already being downloaded!"
        )
        
    async def test_download_progress(self):
        """Test download progress tracking."""
        # Mock message
        message = mock.AsyncMock()
        message.document = mock.AsyncMock()
        message.document.file_id = "test_file_id"
        message.document.file_name = "test.mp4"
        message.document.file_size = 1024 * 100  # 100KB
        
        # Mock bot methods
        self.downloader.bot = mock.AsyncMock()
        self.downloader.bot.get_file.return_value = mock.AsyncMock()
        
        # Create chunks for 50% progress
        chunk_size = 1024
        chunks = [b"x" * chunk_size] * 50  # 50KB
        self.downloader.bot.download_file.return_value = chunks
        
        # Process media
        await self.downloader._process_media(message)
        
        # Verify progress notification
        progress_calls = [
            call for call in self.notification.notify.call_args_list
            if "Downloading test.mp4:" in call.args[0]
        ]
        self.assertGreater(len(progress_calls), 0)
        
        # Verify final notification
        final_call = self.notification.notify.call_args_list[-1]
        self.assertEqual(
            final_call.args[0],
            "Download complete: test.mp4"
        )