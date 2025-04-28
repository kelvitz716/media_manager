"""Tests for configuration manager module."""
import os
import json
import pytest
import tempfile
from pathlib import Path
from media_manager.common.config_manager import ConfigManager, DEFAULT_CONFIG

@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    temp = tempfile.NamedTemporaryFile(mode='w', delete=False)
    config = {
        "tmdb": {"api_key": "test_api_key"},
        "logging": {"level": "DEBUG", "max_size_mb": "10"},
        "notification": {
            "enabled": True,
            "method": "telegram",
            "bot_token": "test_bot_token",
            "chat_id": "test_chat_id"
        }
    }
    json.dump(config, temp)
    temp.close()
    yield temp.name
    os.unlink(temp.name)

def test_load_config(temp_config_file):
    """Test loading configuration from file."""
    config_manager = ConfigManager(temp_config_file)
    assert config_manager.config["tmdb"]["api_key"] == "test_api_key"
    assert config_manager.config["logging"]["level"] == "DEBUG"

def test_load_nonexistent_config():
    """Test loading from nonexistent config file."""
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "nonexistent", "config.json")
    config_manager = ConfigManager(config_path)
    assert config_manager.config == DEFAULT_CONFIG

def test_validate_config_defaults():
    """Test default values are set for missing configuration."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump({"tmdb": {"api_key": "test"}}, f)

    config_manager = ConfigManager(f.name)
    assert config_manager.config["logging"]["level"] == "INFO"
    assert config_manager.config["telegram"]["enabled"] is True
    os.unlink(f.name)

def test_env_override():
    """Test environment variable override."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump(DEFAULT_CONFIG, f)
    
    test_api_key = "test_env_key"
    os.environ["TMDB_API_KEY"] = test_api_key
    
    config_manager = ConfigManager(f.name)
    assert config_manager.config["tmdb"]["api_key"] == test_api_key
    
    del os.environ["TMDB_API_KEY"]
    os.unlink(f.name)

def test_save_config():
    """Test saving configuration."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        # Clear any existing env vars
        if "TMDB_API_KEY" in os.environ:
            del os.environ["TMDB_API_KEY"]
        
        # Create initial config
        initial_config = DEFAULT_CONFIG.copy()
        json.dump(initial_config, f)
        f.close()
        
        # Update and save config
        config_manager = ConfigManager(f.name)
        config_manager.config["tmdb"]["api_key"] = "new_api_key"
        config_manager.save()
        
        # Load saved config
        with open(f.name, 'r') as saved:
            loaded_config = json.load(saved)
            assert loaded_config["tmdb"]["api_key"] == "new_api_key"
        
        os.unlink(f.name)

def test_invalid_json_config():
    """Test handling invalid JSON in config file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("invalid json content")
    
    config_manager = ConfigManager(f.name)
    assert config_manager.config == DEFAULT_CONFIG
    os.unlink(f.name)

def test_config_type_validation():
    """Test type validation and conversion."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        config = {
            "logging": {
                "level": "DEBUG",
                "max_size_mb": "10",  # String that should be converted to int
                "backup_count": "invalid"  # Should use default
            }
        }
        json.dump(config, f)
    
    config_manager = ConfigManager(f.name)
    assert isinstance(config_manager.config["logging"]["max_size_mb"], int)
    assert config_manager.config["logging"]["max_size_mb"] == 10
    assert config_manager.config["logging"]["backup_count"] == DEFAULT_CONFIG["logging"]["backup_count"]
    os.unlink(f.name)

def test_notification_telegram_sync():
    """Test notification and telegram settings sync."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        config = DEFAULT_CONFIG.copy()
        config["telegram"]["bot_token"] = "test_token"
        config["telegram"]["chat_id"] = "test_chat"
        json.dump(config, f)
    
    config_manager = ConfigManager(f.name)
    assert config_manager.config["notification"]["bot_token"] == "test_token"
    assert config_manager.config["notification"]["chat_id"] == "test_chat"
    os.unlink(f.name)

def test_config_creation_error():
    """Test error handling during config creation."""
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "nonexistent", "config.json")
    config_manager = ConfigManager(config_path)
    assert config_manager.config == DEFAULT_CONFIG