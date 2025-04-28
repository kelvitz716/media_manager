"""Tests for manual media categorization."""
import os
import tempfile
from unittest import IsolatedAsyncioTestCase, mock
from media_manager.common.notification_service import NotificationService
from media_manager.watcher.manual_categorizer import ManualCategorizer
from media_manager.watcher.categorizer import MediaCategorizer

class TestManualCategorizer(IsolatedAsyncioTestCase):
    """Test cases for ManualCategorizer."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "paths": {
                "movies_dir": os.path.join(self.temp_dir, "movies"),
                "tv_shows_dir": os.path.join(self.temp_dir, "tv_shows"),
                "unmatched_dir": os.path.join(self.temp_dir, "unmatched")
            },
            "tmdb": {
                "api_key": "test_api_key"
            }
        }
        # Create directories
        for path in self.config["paths"].values():
            os.makedirs(path)
            
        self.notification = mock.AsyncMock(spec=NotificationService)
        self.categorizer = mock.AsyncMock(spec=MediaCategorizer)
        self.manual = ManualCategorizer(
            self.config,
            self.notification,
            self.categorizer
        )
        
    async def asyncTearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            
    def test_get_unmatched_files(self):
        """Test getting list of unmatched files."""
        # Create test files
        files = ["test1.mp4", "test2.mkv", "test3.avi"]
        for file in files:
            path = os.path.join(self.config["paths"]["unmatched_dir"], file)
            with open(path, "wb") as f:
                f.write(b"test content")
                
        # Get unmatched files
        result = self.manual._get_unmatched_files()
        
        # Verify results
        self.assertEqual(len(result), 3)
        self.assertTrue(all(
            os.path.basename(f) in files 
            for f in result
        ))
        
    async def test_start_categorization(self):
        """Test starting categorization session."""
        # Create test file
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Mock notification response
        self.notification.wait_for_response.side_effect = [
            "1",  # Select movie
            "Test Movie",  # Movie title
            "2024"  # Year
        ]
        
        # Start categorization
        await self.manual._start_categorization(test_file)
        
        # Verify session was created with correct metadata
        async with self.manual._session_lock:
            self.assertIn(test_file, self.manual._active_sessions)
            self.assertEqual(
                self.manual._active_sessions[test_file]["metadata"]["type"],
                "movie"
            )
            self.assertEqual(
                self.manual._active_sessions[test_file]["metadata"]["title"],
                "Test Movie"
            )
            self.assertEqual(
                self.manual._active_sessions[test_file]["metadata"]["year"],
                2024
            )
            
    async def test_process_movie_details(self):
        """Test processing movie details."""
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Set up session
        async with self.manual._session_lock:
            self.manual._active_sessions[test_file] = {
                "stage": "details",
                "metadata": {"type": "movie"}
            }
            
        # Mock successful media processing
        self.categorizer._process_movie.return_value = True
            
        # Mock notification responses
        self.notification.wait_for_response.side_effect = [
            "The Movie",  # Title
            "2024"       # Year
        ]
        
        # Get movie details
        await self.manual._get_movie_details(test_file)
        
        # Verify metadata was updated and processed
        self.categorizer._process_movie.assert_called_once_with(
            test_file,
            {"title": "The Movie", "year": 2024}
        )
        
        # Verify session was cleared after successful processing
        async with self.manual._session_lock:
            self.assertNotIn(test_file, self.manual._active_sessions)
            
    async def test_process_tv_show_details(self):
        """Test processing TV show details."""
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        
        # Set up session
        async with self.manual._session_lock:
            self.manual._active_sessions[test_file] = {
                "stage": "details",
                "metadata": {"type": "tv"}
            }
            
        # Mock notification responses
        self.notification.wait_for_response.side_effect = [
            "Show Name",  # Title
            "1",         # Season
            "2"          # Episode
        ]
        
        # Get TV show details
        await self.manual._get_tv_show_details(test_file)
        
        # Verify metadata was updated
        async with self.manual._session_lock:
            metadata = self.manual._active_sessions[test_file]["metadata"]
            self.assertEqual(metadata["show"], "Show Name")
            self.assertEqual(metadata["season"], 1)
            self.assertEqual(metadata["episode"], 2)
            
    async def test_handle_commands(self):
        """Test command handling."""
        # Create test files
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Test /list command
        message = mock.AsyncMock()
        await self.manual._handle_list(message)
        
        # Verify list was sent
        self.notification.notify.assert_called_with(
            mock.ANY,
            level="info"
        )
        list_msg = self.notification.notify.call_args[0][0]
        self.assertIn("test.mp4", list_msg)
        
        # Test /skip command with no active session
        await self.manual._handle_skip(message)
        self.notification.notify.assert_called_with(
            "No active categorization session",
            level="warning"
        )
        
    async def test_process_file_completion(self):
        """Test complete file processing."""
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Set up session with movie metadata
        async with self.manual._session_lock:
            self.manual._active_sessions[test_file] = {
                "stage": "details",
                "metadata": {
                    "type": "movie",
                    "title": "Test Movie",
                    "year": 2024
                }
            }
        
        # Process the file
        await self.manual._process_file(test_file)
        
        # Verify categorizer was called
        self.categorizer._process_movie.assert_called_once_with(
            test_file,
            {"title": "Test Movie", "year": 2024}
        )
        
        # Verify session was cleared
        async with self.manual._session_lock:
            self.assertNotIn(test_file, self.manual._active_sessions)
        
        # Verify success notification
        self.notification.notify.assert_called_with(
            "Successfully categorized: test.mp4",
            level="success"
        )
        
    async def test_invalid_input_handling(self):
        """Test handling of invalid inputs."""
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Test invalid media type selection
        self.notification.wait_for_response.return_value = "3"  # Invalid option
        await self.manual._start_categorization(test_file)
        
        self.notification.notify.assert_called_with(
            "Invalid selection. Please try again.",
            level="warning"
        )
        
        # Test invalid season number
        async with self.manual._session_lock:
            self.manual._active_sessions[test_file] = {
                "stage": "details",
                "metadata": {"type": "tv"}
            }
            
        self.notification.wait_for_response.side_effect = [
            "Show Name",  # Title
            "invalid",   # Invalid season
            "1",        # Valid season
            "2"         # Episode
        ]
        
        await self.manual._get_tv_show_details(test_file)
        
        # Verify error notification was sent
        notify_calls = self.notification.notify.call_args_list
        self.assertTrue(
            any(
                call[0][0] == "Invalid season number. Please try again."
                and call[1]["level"] == "warning"
                for call in notify_calls
            )
        )
        
    async def test_timeout_handling(self):
        """Test handling of response timeouts."""
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Set up session
        async with self.manual._session_lock:
            self.manual._active_sessions[test_file] = {
                "stage": "details",
                "metadata": {"type": "movie"}
            }
            
        # Simulate timeout by returning None
        self.notification.wait_for_response.return_value = None
        
        # Get movie details
        await self.manual._get_movie_details(test_file)
        
        # Verify session was cleared
        async with self.manual._session_lock:
            self.assertNotIn(test_file, self.manual._active_sessions)
        
        # Verify timeout notification
        self.notification.notify.assert_called_with(
            "Categorization cancelled due to timeout.",
            level="warning"
        )