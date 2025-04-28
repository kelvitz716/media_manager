"""Tests for Telegram downloader bot."""
import os
import tempfile
from unittest import IsolatedAsyncioTestCase, mock
from media_manager.common.notification_service import NotificationService
from media_manager.downloader.bot import TelegramDownloader

class AsyncIterator:
    """Helper class to mock async iterators."""
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return self.items.pop(0)
        except IndexError:
            raise StopAsyncIteration

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
                "bot_token": "123456:test_bot_token",
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
        message = mock.AsyncMock()
        message.document = mock.AsyncMock()
        message.document.file_id = "test_file_id"
        message.document.file_name = "test.mp4"
        message.document.file_size = 1024
        
        self.downloader.bot = mock.AsyncMock()
        file_mock = mock.AsyncMock()
        file_mock.file_path = "test/path"
        self.downloader.bot.get_file.return_value = file_mock
        
        # Set up download_file to return the iterator directly
        iterator = AsyncIterator([b"test_data"])
        self.downloader.bot.download_file = mock.Mock(return_value=iterator)
        
        await self.downloader._process_media(message)
        
        self.downloader.bot.get_file.assert_called_once_with("test_file_id")
        self.downloader.bot.download_file.assert_called_once_with(
            "test/path",
            chunk_size=1024
        )
        
        self.notification.notify.assert_called_with(
            "Download complete: test.mp4",
            level="success"
        )
        
    async def test_process_media_video(self):
        """Test processing media video."""
        message = mock.AsyncMock()
        message.video = mock.AsyncMock()
        message.video.file_id = "test_file_id"
        message.video.file_name = "test.mp4"
        message.video.file_size = 1024
        message.document = None
        
        self.downloader.bot = mock.AsyncMock()
        file_mock = mock.AsyncMock()
        file_mock.file_path = "test/path"
        self.downloader.bot.get_file.return_value = file_mock
        
        # Set up download_file to return the iterator directly
        iterator = AsyncIterator([b"test_data"])
        self.downloader.bot.download_file = mock.Mock(return_value=iterator)
        
        await self.downloader._process_media(message)
        
        self.downloader.bot.get_file.assert_called_once_with("test_file_id")
        self.downloader.bot.download_file.assert_called_once_with(
            "test/path",
            chunk_size=1024
        )
        
        self.notification.notify.assert_called_with(
            "Download complete: test.mp4",
            level="success"
        )
        
    async def test_download_progress(self):
        """Test download progress tracking."""
        message = mock.AsyncMock()
        message.document = mock.AsyncMock()
        message.document.file_id = "test_file_id"
        message.document.file_name = "test.mp4"
        message.document.file_size = 1024 * 100  # 100KB
        
        self.downloader.bot = mock.AsyncMock()
        file_mock = mock.AsyncMock()
        file_mock.file_path = "test/path"
        self.downloader.bot.get_file.return_value = file_mock
        
        # Create chunks for 50% progress
        chunk_size = 1024
        chunks = [b"x" * chunk_size] * 50  # 50KB
        iterator = AsyncIterator(chunks)
        self.downloader.bot.download_file = mock.Mock(return_value=iterator)
        
        await self.downloader._process_media(message)
        
        progress_calls = [
            call for call in self.notification.notify.call_args_list
            if "Downloading test.mp4:" in call.args[0]
        ]
        self.assertGreater(len(progress_calls), 0)
        
        final_call = self.notification.notify.call_args_list[-1]
        self.assertEqual(
            final_call.args[0],
            "Download complete: test.mp4"
        )