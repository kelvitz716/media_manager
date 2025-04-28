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
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump({}, f)
    yield f.name
    os.unlink(f.name)

def test_load_config(temp_config_file):
    """Test loading configuration from file."""
    manager = ConfigManager(temp_config_file)
    assert manager.config == DEFAULT_CONFIG

def test_load_nonexistent_config():
    """Test loading from nonexistent config file."""
    manager = ConfigManager("nonexistent.json")
    assert manager.config == DEFAULT_CONFIG

def test_validate_config_defaults():
    """Test default values are set for missing configuration."""
    config = {}
    manager = ConfigManager()
    manager.config = config
    manager._validate_config()
    assert manager.config["logging"]["level"] == DEFAULT_CONFIG["logging"]["level"]

def test_env_override():
    """Test environment variable override."""
    os.environ["LOG_LEVEL"] = "DEBUG"
    manager = ConfigManager()
    assert manager.config["logging"]["level"] == "DEBUG"
    os.environ.pop("LOG_LEVEL")

def test_save_config(temp_config_file):
    """Test saving configuration."""
    manager = ConfigManager(temp_config_file)
    manager.config["test_key"] = "test_value"
    manager.save()
    
    with open(temp_config_file, 'r') as f:
        saved_config = json.load(f)
    assert saved_config["test_key"] == "test_value"

def test_invalid_json_config():
    """Test handling invalid JSON in config file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("invalid json")
        f.flush()
    
    manager = ConfigManager(f.name)
    assert manager.config == DEFAULT_CONFIG
    os.unlink(f.name)

def test_config_type_validation():
    """Test type validation and conversion."""
    config = {
        "download": {
            "max_retries": "3",
            "chunk_size": "1024",
            "progress_update_interval": "5"
        }
    }
    manager = ConfigManager()
    manager.config = config
    manager._validate_config()
    
    assert isinstance(manager.config["download"]["max_retries"], int)
    assert isinstance(manager.config["download"]["chunk_size"], int)
    assert isinstance(manager.config["download"]["progress_update_interval"], int)
    assert manager.config["download"]["max_retries"] == 3
    assert manager.config["download"]["chunk_size"] == 1024
    assert manager.config["download"]["progress_update_interval"] == 5

def test_notification_telegram_sync():
    """Test notification and telegram settings sync."""
    config = {
        "notification": {
            "enabled": True,
            "method": "telegram",
            "bot_token": "test_token",
            "chat_id": "test_chat"
        }
    }
    manager = ConfigManager()
    manager.config = config
    manager._validate_config()
    
    assert manager.config["telegram"]["bot_token"] == "test_token"
    assert manager.config["telegram"]["chat_id"] == "test_chat"

def test_config_creation_error():
    """Test error handling during config creation."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("{}")
        f.flush()
    os.chmod(f.name, 0o444)  # Make file read-only
    
    manager = ConfigManager(f.name)
    manager.config["test"] = "value"
    # Should not raise exception when saving to read-only file
    manager.save()  
    
    os.chmod(f.name, 0o666)  # Restore permissions
    os.unlink(f.name)