"""Tests for the configuration management component."""
import os
import json
import pytest
from typing import Dict, Any
from unittest import mock
from media_manager.common.config_manager import ConfigManager

@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file."""
    config = {
        "paths": {
            "telegram_download_dir": "downloads",
            "movies_dir": "media/movies",
            "tv_shows_dir": "media/tv_shows",
            "unmatched_dir": "media/unmatched"
        },
        "tmdb": {
            "api_key": "test_api_key"
        },
        "telegram": {
            "api_id": "test_id",
            "api_hash": "test_hash",
            "bot_token": "test_token",
            "enabled": True,
            "chat_id": "123456789"
        }
    }
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(config, f)
    return str(config_file)

@pytest.fixture
def config_manager(temp_config_file):
    """Create ConfigManager instance."""
    return ConfigManager(temp_config_file)

def test_load_config(temp_config_file):
    """Test loading configuration from file."""
    manager = ConfigManager(temp_config_file)
    assert manager.config["tmdb"]["api_key"] == "test_api_key"
    assert manager.config["telegram"]["bot_token"] == "test_token"

def test_load_nonexistent_config(tmp_path):
    """Test loading from nonexistent file creates default config."""
    config_file = tmp_path / "nonexistent.json"
    manager = ConfigManager(str(config_file))
    
    # Should create default config
    assert os.path.exists(config_file)
    assert "paths" in manager.config
    assert "tmdb" in manager.config
    assert "telegram" in manager.config

def test_validate_config_defaults(tmp_path):
    """Test validation adds missing defaults."""
    # Create minimal config
    config_file = tmp_path / "minimal.json"
    with open(config_file, "w") as f:
        json.dump({"tmdb": {"api_key": "test_key"}}, f)
    
    manager = ConfigManager(str(config_file))
    
    # Check defaults were added
    assert "paths" in manager.config
    assert "telegram" in manager.config
    assert "logging" in manager.config
    assert "download" in manager.config
    assert manager.config["paths"]["movies_dir"] == "media/movies"

def test_env_override(temp_config_file):
    """Test environment variable overrides."""
    env_vars = {
        "TELEGRAM_API_ID": "env_api_id",
        "TELEGRAM_API_HASH": "env_api_hash",
        "TELEGRAM_BOT_TOKEN": "env_bot_token",
        "TELEGRAM_CHAT_ID": "987654321",
        "TMDB_API_KEY": "env_tmdb_key",
        "LOG_LEVEL": "DEBUG"
    }
    
    with mock.patch.dict(os.environ, env_vars):
        manager = ConfigManager(temp_config_file)
        
        # Check environment overrides
        assert manager.config["telegram"]["api_id"] == "env_api_id"
        assert manager.config["telegram"]["api_hash"] == "env_api_hash"
        assert manager.config["telegram"]["bot_token"] == "env_bot_token"
        assert manager.config["telegram"]["chat_id"] == "987654321"
        assert manager.config["tmdb"]["api_key"] == "env_tmdb_key"
        assert manager.config["logging"]["level"] == "DEBUG"

def test_save_config(temp_config_file):
    """Test saving configuration changes."""
    manager = ConfigManager(temp_config_file)
    
    # Modify config
    manager.config["tmdb"]["api_key"] = "new_key"
    manager.save()
    
    # Load new instance and verify changes
    new_manager = ConfigManager(temp_config_file)
    assert new_manager.config["tmdb"]["api_key"] == "new_key"

def test_invalid_json_config(tmp_path):
    """Test handling of invalid JSON config."""
    config_file = tmp_path / "invalid.json"
    with open(config_file, "w") as f:
        f.write("invalid json content")
    
    # Should load default config
    manager = ConfigManager(str(config_file))
    assert "paths" in manager.config
    assert "tmdb" in manager.config

def test_config_type_validation(temp_config_file):
    """Test validation of config value types."""
    manager = ConfigManager(temp_config_file)
    
    # Test with invalid types
    manager.config["logging"]["max_size_mb"] = "10"  # Should be int
    manager.config["telegram"]["enabled"] = "true"  # Should be bool
    
    # Validate should fix types
    manager._validate_config()
    
    assert isinstance(manager.config["logging"]["max_size_mb"], int)
    assert isinstance(manager.config["telegram"]["enabled"], bool)

def test_notification_telegram_sync(temp_config_file):
    """Test synchronization of notification telegram settings."""
    manager = ConfigManager(temp_config_file)
    
    # Set telegram settings
    manager.config["telegram"]["bot_token"] = "new_token"
    manager.config["telegram"]["chat_id"] = "new_chat_id"
    
    # Validate should sync to notification section
    manager._validate_config()
    
    assert manager.config["notification"]["bot_token"] == "new_token"
    assert manager.config["notification"]["chat_id"] == "new_chat_id"

def test_config_creation_error(tmp_path):
    """Test handling of config creation errors."""
    # Try to create config in non-existent directory
    config_file = tmp_path / "nonexistent" / "config.json"
    
    # Should fall back to default config in memory
    manager = ConfigManager(str(config_file))
    assert "paths" in manager.config
    assert "tmdb" in manager.config