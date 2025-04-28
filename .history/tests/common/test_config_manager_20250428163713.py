"""Tests for configuration management."""
import os
import json
import pytest
import tempfile
from pathlib import Path
from media_manager.common.config_manager import ConfigManager, DEFAULT_CONFIG

@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
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
        json.dump(config, f)
        f.flush()
        yield f.name
    Path(f.name).unlink(missing_ok=True)

def test_load_config(temp_config_file):
    """Test loading configuration from file."""
    # Set environment variable
    os.environ["TMDB_API_KEY"] = "test_api_key"
    
    manager = ConfigManager(temp_config_file)
    assert isinstance(manager.config, dict)
    assert manager.config["tmdb"]["api_key"] == "test_api_key"
    assert manager.config["logging"]["level"] == "DEBUG"
    
    # Clean up
    del os.environ["TMDB_API_KEY"]

def test_load_nonexistent_config():
    """Test loading nonexistent configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "nonexistent", "config.json")
        manager = ConfigManager(config_path)
        assert manager.config == DEFAULT_CONFIG

def test_validate_config_defaults():
    """Test default values are set for missing configuration."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        json.dump({"tmdb": {"api_key": "test"}}, f)
        f.flush()
        manager = ConfigManager(f.name)
        
        # Check defaults are set
        for section, defaults in DEFAULT_CONFIG.items():
            assert section in manager.config
            for key, value in defaults.items():
                assert key in manager.config[section]
    
    Path(f.name).unlink(missing_ok=True)

def test_env_override():
    """Test environment variable override."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        json.dump(DEFAULT_CONFIG, f)
        f.flush()
        
        # Set environment variables
        os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
        os.environ["LOG_LEVEL"] = "DEBUG"
        
        manager = ConfigManager(f.name)
        assert manager.config["telegram"]["bot_token"] == "test_token"
        assert manager.config["logging"]["level"] == "DEBUG"
        
        # Clean up
        del os.environ["TELEGRAM_BOT_TOKEN"]
        del os.environ["LOG_LEVEL"]
    
    Path(f.name).unlink(missing_ok=True)

def test_save_config():
    """Test saving configuration."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        # Create initial config
        json.dump(DEFAULT_CONFIG, f)
        f.flush()
        
        # Modify and save
        manager = ConfigManager(f.name)
        manager.config["tmdb"]["api_key"] = "new_key"
        manager.save()
        
        # Load again and verify
        new_manager = ConfigManager(f.name)
        assert new_manager.config["tmdb"]["api_key"] == "new_key"
    
    Path(f.name).unlink(missing_ok=True)

def test_invalid_json_config():
    """Test handling invalid JSON configuration."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"invalid json")
        f.flush()
        
        manager = ConfigManager(f.name)
        assert manager.config == DEFAULT_CONFIG
    
    Path(f.name).unlink(missing_ok=True)

def test_config_type_validation():
    """Test type validation and conversion."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        config = {
            "logging": {
                "level": "DEBUG",
                "max_size_mb": "10",  # String that should be converted to int
                "backup_count": "invalid"  # Should use default
            }
        }
        json.dump(config, f)
        f.flush()
        
        manager = ConfigManager(f.name)
        assert isinstance(manager.config["logging"]["max_size_mb"], int)
        assert manager.config["logging"]["max_size_mb"] == 10
        assert manager.config["logging"]["backup_count"] == DEFAULT_CONFIG["logging"]["backup_count"]
    
    Path(f.name).unlink(missing_ok=True)

def test_notification_telegram_sync():
    """Test notification and telegram settings sync."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        config = DEFAULT_CONFIG.copy()
        json.dump(config, f)
        f.flush()
        
        os.environ["TELEGRAM_BOT_TOKEN"] = "new_token"
        manager = ConfigManager(f.name)
        
        assert manager.config["telegram"]["bot_token"] == "new_token"
        assert manager.config["notification"]["bot_token"] == "new_token"
        
        del os.environ["TELEGRAM_BOT_TOKEN"]
    
    Path(f.name).unlink(missing_ok=True)

def test_config_creation_error():
    """Test error handling during config creation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Make directory read-only
        os.chmod(temp_dir, 0o444)
        
        config_path = os.path.join(temp_dir, "config.json")
        manager = ConfigManager(config_path)
        
        # Should use default config when save fails
        assert manager.config == DEFAULT_CONFIG