"""Tests for configuration management."""
import os
import json
import tempfile
from unittest import TestCase, mock
from media_manager.common.config_manager import ConfigManager

class TestConfigManager(TestCase):
    """Test cases for ConfigManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config.json")
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            
    def test_create_default_config(self):
        """Test creation of default configuration."""
        manager = ConfigManager(self.config_path)
        self.assertTrue(os.path.exists(self.config_path))
        
        with open(self.config_path) as f:
            config = json.load(f)
            
        self.assertIn("paths", config)
        self.assertIn("telegram", config)
        self.assertIn("logging", config)
        
    @mock.patch.dict(os.environ, {
        "TELEGRAM_API_ID": "test_api_id",
        "TELEGRAM_BOT_TOKEN": "test_bot_token",
        "TMDB_API_KEY": "test_tmdb_key",
        "LOG_LEVEL": "DEBUG"
    })
    def test_env_override(self):
        """Test environment variable overrides."""
        manager = ConfigManager(self.config_path)
        
        self.assertEqual(manager.config["telegram"]["api_id"], "test_api_id")
        self.assertEqual(manager.config["telegram"]["bot_token"], "test_bot_token")
        self.assertEqual(manager.config["tmdb"]["api_key"], "test_tmdb_key")
        self.assertEqual(manager.config["logging"]["level"], "DEBUG")
        
    def test_get_config_value(self):
        """Test getting configuration values."""
        manager = ConfigManager(self.config_path)
        
        # Test existing value
        self.assertEqual(
            manager.get("logging", "level"),
            "INFO"
        )
        
        # Test default value
        self.assertEqual(
            manager.get("nonexistent", "key", "default"),
            "default"
        )
        
    def test_save_config(self):
        """Test saving configuration changes."""
        manager = ConfigManager(self.config_path)
        
        # Modify configuration
        manager.config["test_section"] = {"test_key": "test_value"}
        manager.save()
        
        # Read config file directly
        with open(self.config_path) as f:
            saved_config = json.load(f)
            
        self.assertIn("test_section", saved_config)
        self.assertEqual(
            saved_config["test_section"]["test_key"],
            "test_value"
        )