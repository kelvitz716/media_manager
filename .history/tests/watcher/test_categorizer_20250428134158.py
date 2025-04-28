"""Tests for media categorization."""
import os
import tempfile
from unittest import IsolatedAsyncioTestCase, mock
from media_manager.common.notification_service import NotificationService
from media_manager.watcher.categorizer import MediaCategorizer

class TestMediaCategorizer(IsolatedAsyncioTestCase):
    """Test cases for MediaCategorizer."""
    
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
        self.categorizer = MediaCategorizer(self.config, self.notification)
        
    async def asyncTearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            
    def test_parse_movie_filename(self):
        """Test movie filename parsing."""
        test_cases = [
            ("The.Movie.2024.mp4", ("movie", {"title": "The Movie", "year": "2024"})),
            ("The Movie (2024).mkv", ("movie", {"title": "The Movie", "year": "2024"})),
            ("Invalid.File.mp4", (None, None))
        ]
        
        for filename, expected in test_cases:
            result = self.categorizer._parse_filename(filename)
            self.assertEqual(result, expected)
            
    def test_parse_tv_show_filename(self):
        """Test TV show filename parsing."""
        test_cases = [
            ("Show.Name.S01E02.mp4", ("tv", {
                "show": "Show Name",
                "season": "01",
                "episode": "02"
            })),
            ("Show.Name.1x02.mkv", ("tv", {
                "show": "Show Name",
                "season": "1",
                "episode": "02"
            })),
            ("Invalid.File.mp4", (None, None))
        ]
        
        for filename, expected in test_cases:
            result = self.categorizer._parse_filename(filename)
            self.assertEqual(result, expected)
            
    async def test_process_movie(self):
        """Test movie processing."""
        # Create test file
        test_file = os.path.join(self.temp_dir, "The.Movie.2024.mp4")
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Mock TMDB response
        self.categorizer.tmdb.search_movie = mock.AsyncMock()
        self.categorizer.tmdb.search_movie.return_value = {
            "title": "The Movie",
            "year": "2024",
            "id": "123"
        }
        
        # Process file
        success = await self.categorizer.process_file(test_file)
        self.assertTrue(success)
        
        # Verify file was moved
        expected_path = os.path.join(
            self.config["paths"]["movies_dir"],
            "The Movie (2024)",
            "The.Movie.2024.mp4"
        )
        self.assertTrue(os.path.exists(expected_path))
        
    async def test_process_tv_show(self):
        """Test TV show processing."""
        # Create test file
        test_file = os.path.join(self.temp_dir, "Show.Name.S01E02.mp4")
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Mock TMDB response
        self.categorizer.tmdb.search_tv_show = mock.AsyncMock()
        self.categorizer.tmdb.search_tv_show.return_value = {
            "name": "Show Name",
            "id": "123"
        }
        
        # Process file
        success = await self.categorizer.process_file(test_file)
        self.assertTrue(success)
        
        # Verify file was moved
        expected_path = os.path.join(
            self.config["paths"]["tv_shows_dir"],
            "Show Name",
            "Season 01",
            "Show.Name.S01E02.mp4"
        )
        self.assertTrue(os.path.exists(expected_path))
        
    async def test_unmatched_file(self):
        """Test handling of unmatched files."""
        # Create test file
        test_file = os.path.join(self.temp_dir, "Invalid.File.mp4")
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Process file
        success = await self.categorizer.process_file(test_file)
        self.assertFalse(success)
        
        # Verify notification
        self.notification.notify.assert_called_with(
            "Unable to automatically categorize: Invalid.File.mp4\n"
            "Please use /categorize to process manually.",
            level="warning"
        )
        
    async def test_move_to_unmatched(self):
        """Test moving file to unmatched directory."""
        # Create test file
        test_file = os.path.join(self.temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"test content")
            
        # Move to unmatched
        await self.categorizer.move_to_unmatched(test_file)
        
        # Verify file was moved
        expected_path = os.path.join(
            self.config["paths"]["unmatched_dir"],
            "test.mp4"
        )
        self.assertTrue(os.path.exists(expected_path))
        
        # Verify notification
        self.notification.notify.assert_called_with(
            "Moved to unmatched: test.mp4",
            level="info"
        )