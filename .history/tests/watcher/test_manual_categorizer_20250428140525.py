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
            
        # Start categorization
        await self.manual._start_categorization(test_file)
        
        # Verify session was created with initial state
        async with self.manual._session_lock:
            self.assertIn(test_file, self.manual._active_sessions)
            self.assertEqual(
                self.manual._active_sessions[test_file]["stage"],
                "type"
            )
            self.assertIn("last_activity", self.manual._active_sessions[test_file])
            self.assertEqual(
                len(self.manual._active_sessions[test_file]["metadata"]),
                0
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
        with open(test_file, "wb") as f:
            f.write(b"test content")

        # Set up session
        async with self.manual._session_lock:
            self.manual._active_sessions[test_file] = {
                "stage": "details",
                "metadata": {"type": "tv"}
            }
            
        # Mock successful media processing
        self.categorizer._process_tv_show.return_value = True

        # Mock notification responses
        self.notification.wait_for_response.side_effect = [
            "Show Name",  # Title
            "1",         # Season
            "2"          # Episode
        ]
        
        # Get TV show details
        await self.manual._get_tv_show_details(test_file)
        
        # Verify metadata was processed correctly
        self.categorizer._process_tv_show.assert_called_once_with(
            test_file,
            {"show": "Show Name", "season": 1, "episode": 2}
        )
        
        # Verify session was cleared after successful processing
        async with self.manual._session_lock:
            self.assertNotIn(test_file, self.manual._active_sessions)
            
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
        
        # Mock successful categorization
        self.categorizer._process_movie.return_value = True
            
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
        
        # Verify categorizer was called correctly
        self.categorizer._process_movie.assert_called_once_with(
            test_file,
            {"title": "Test Movie", "year": 2024}
        )
        
        # Verify session was cleared
        async with self.manual._session_lock:
            self.assertNotIn(test_file, self.manual._active_sessions)
        
        # Verify notifications in order
        self.notification.notify.assert_has_calls([
            mock.call(
                "Successfully categorized: test.mp4",
                level="success"
            ),
            mock.call(
                mock.ANY,  # Don't check exact remaining files message
                level="info"
            )
        ], any_order=False)
        
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
        
    async def test_continue_iteration(self):
        """Test continuing iteration through multiple files."""
        # Create multiple test files in a specific order
        files = sorted(["test1.mp4", "test2.mkv", "test3.avi"])  # Sort to ensure consistent order
        test_files = []
        for file in files:
            path = os.path.join(self.config["paths"]["unmatched_dir"], file)
            with open(path, "wb") as f:
                f.write(b"test content")
            test_files.append(path)

        # Mock successful categorization and actually move the files
        async def process_movie_mock(file_path, metadata):
            # Move file to movies dir to simulate successful processing
            new_path = os.path.join(
                self.config["paths"]["movies_dir"],
                os.path.basename(file_path)
            )
            os.rename(file_path, new_path)
            return True

        self.categorizer._process_movie = mock.AsyncMock(side_effect=process_movie_mock)
            
        # Process first file
        async with self.manual._session_lock:
            self.manual._active_sessions[test_files[0]] = {
                "stage": "details",
                "metadata": {
                    "type": "movie",
                    "title": "Test Movie 1",
                    "year": 2024
                }
            }
        
        # Before processing, we should have 3 files
        unmatched_before = self.manual._get_unmatched_files()
        self.assertEqual(len(unmatched_before), 3)

        # Process first file
        await self.manual._process_file(test_files[0])
        
        # After processing first file, we should have 2 files
        unmatched_after = self.manual._get_unmatched_files()
        self.assertEqual(len(unmatched_after), 2)

        # Verify notifications
        self.notification.notify.assert_has_calls([
            mock.call(
                "Successfully categorized: test1.mp4",
                level="success"
            ),
            mock.call(
                "2 files remaining to categorize",
                level="info"
            )
        ], any_order=False)

        # Reset mocks for next test
        self.categorizer._process_movie.reset_mock()
        self.notification.notify.reset_mock()

        # Process second file
        async with self.manual._session_lock:
            self.manual._active_sessions[test_files[1]] = {
                "stage": "details",
                "metadata": {
                    "type": "movie",
                    "title": "Test Movie 2",
                    "year": 2024
                }
            }
        
        # Process second file
        await self.manual._process_file(test_files[1])

        # After processing second file, we should have 1 file
        unmatched_final = self.manual._get_unmatched_files()
        self.assertEqual(len(unmatched_final), 1)
        
        # Verify notifications
        self.notification.notify.assert_has_calls([
            mock.call(
                "Successfully categorized: test2.mkv",
                level="success"
            ),
            mock.call(
                "1 file remaining to categorize",
                level="info"
            )
        ], any_order=False)
        
    async def test_file_operation_errors(self):
        """Test handling of file system operation errors."""
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        
        # Test file not found during processing
        async with self.manual._session_lock:
            self.manual._active_sessions[test_file] = {
                "stage": "details",
                "metadata": {
                    "type": "movie",
                    "title": "Test Movie",
                    "year": 2024
                }
            }
            
        # Don't actually create the file to simulate missing file
        await self.manual._process_file(test_file)
        
        # Verify error handling
        self.notification.notify.assert_called_with(
            mock.ANY,  # Don't check exact error message
            level="error"
        )
        
        # Test permission error
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Mock os.rename to raise PermissionError
        with mock.patch('os.rename') as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            
            # Set up session and try to process
            async with self.manual._session_lock:
                self.manual._active_sessions[test_file] = {
                    "stage": "details",
                    "metadata": {
                        "type": "movie",
                        "title": "Test Movie",
                        "year": 2024
                    }
                }
            
            await self.manual._process_file(test_file)
            
            # Verify error notification
            self.notification.notify.assert_called_with(
                mock.ANY,  # Don't check exact error message
                level="error"
            )
            
    async def test_concurrent_session_management(self):
        """Test handling of concurrent categorization sessions."""
        # Create test files
        test_files = [
            os.path.join(self.config["paths"]["unmatched_dir"], f"test{i}.mp4")
            for i in range(3)
        ]
        for file in test_files:
            with open(file, "wb") as f:
                f.write(b"test content")
                
        # Try to start multiple sessions
        tasks = [
            self.manual._start_categorization(file)
            for file in test_files
        ]
        
        # Run concurrently
        await asyncio.gather(*tasks)
        
        # Verify only one session is active
        async with self.manual._session_lock:
            self.assertEqual(len(self.manual._active_sessions), 1)
            
        # Verify correct notification
        self.notification.notify.assert_called_with(
            mock.ANY,  # Don't check exact message
            level="warning"
        )
        
    async def test_session_cleanup_on_error(self):
        """Test session cleanup after errors in different stages."""
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Test cleanup after error in movie details
        self.notification.wait_for_response.side_effect = Exception("Test error")
        
        await self.manual._get_movie_details(test_file)
        
        # Verify session was cleaned up
        async with self.manual._session_lock:
            self.assertNotIn(test_file, self.manual._active_sessions)
            
        # Verify error notification
        self.notification.notify.assert_called_with(
            mock.ANY,  # Don't check exact error message
            level="error"
        )
        
        # Reset mock
        self.notification.wait_for_response.reset_mock()
        self.notification.notify.reset_mock()
        
        # Test cleanup after categorizer error
        self.categorizer._process_movie.side_effect = Exception("Categorizer error")
        
        async with self.manual._session_lock:
            self.manual._active_sessions[test_file] = {
                "stage": "details",
                "metadata": {
                    "type": "movie",
                    "title": "Test Movie",
                    "year": 2024
                }
            }
            
        await self.manual._process_file(test_file)
        
        # Verify session was cleaned up
        async with self.manual._session_lock:
            self.assertNotIn(test_file, self.manual._active_sessions)
            
        # Verify error notification
        self.notification.notify.assert_called_with(
            mock.ANY,  # Don't check exact error message
            level="error"
        )
        
    async def test_filesystem_edge_cases(self):
        """Test handling of filesystem edge cases."""
        # Test with symbolic links
        test_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        symlink = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test_link.mp4"
        )
        
        # Create file and symlink
        with open(test_file, "wb") as f:
            f.write(b"test content")
        os.symlink(test_file, symlink)
        
        # Verify symlinks are handled
        files = self.manual._get_unmatched_files()
        self.assertEqual(len(files), 2)  # Both file and symlink should be included
        
        # Test with special characters in filename
        special_file = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test!@#$%^&*.mp4"
        )
        with open(special_file, "wb") as f:
            f.write(b"test content")
            
        # Set up session with special filename
        async with self.manual._session_lock:
            self.manual._active_sessions[special_file] = {
                "stage": "details",
                "metadata": {
                    "type": "movie",
                    "title": "Test Movie",
                    "year": 2024
                }
            }
            
        # Mock successful categorization
        self.categorizer._process_movie.return_value = True
        
        # Process file with special characters
        await self.manual._process_file(special_file)
        
        # Verify successful processing
        self.notification.notify.assert_called_with(
            mock.ANY,  # Don't check exact success message
            level="success"
        )
        
        # Clean up symlink
        os.unlink(symlink)