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
    # Clear any existing env vars
    if "TMDB_API_KEY" in os.environ:
        del os.environ["TMDB_API_KEY"]
        
    manager = ConfigManager(temp_config_file)
    assert isinstance(manager.config, dict)
    assert manager.config["tmdb"]["api_key"] == "test_api_key"
    assert manager.config["logging"]["level"] == "DEBUG"

def test_load_nonexistent_config():
    """Test loading nonexistent configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "nonexistent", "config.json")
        manager = ConfigManager(config_path)
        assert isinstance(manager.config, dict)
        for section in DEFAULT_CONFIG:
            assert section in manager.config

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
        env_vars = {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "LOG_LEVEL": "DEBUG",
            "TMDB_API_KEY": "test_key",
            "TELEGRAM_CHAT_ID": "test_chat"
        }
        
        # Store original values
        old_env = {}
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        manager = ConfigManager(f.name)
        assert manager.config["telegram"]["bot_token"] == "test_token"
        assert manager.config["logging"]["level"] == "DEBUG"
        assert manager.config["tmdb"]["api_key"] == "test_key"
        assert manager.config["telegram"]["chat_id"] == "test_chat"
        
        # Restore original environment
        for key, value in old_env.items():
            if value is None:
                del os.environ[key]
            else:
                os.environ[key] = value
    
    Path(f.name).unlink(missing_ok=True)

def test_save_config():
    """Test saving configuration."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        # Clear any existing env vars
        if "TMDB_API_KEY" in os.environ:
            del os.environ["TMDB_API_KEY"]
            
        # Create initial config
        initial_config = DEFAULT_CONFIG.copy()
        json.dump(initial_config, f)
        f.flush()
        
        # Modify and save
        manager = ConfigManager(f.name)
        manager.config["tmdb"]["api_key"] = "new_key"
        manager.save()
        
        # Load again and verify
        with open(f.name, 'r') as conf_file:
            saved_config = json.load(conf_file)
        assert saved_config["tmdb"]["api_key"] == "new_key"
        
        # Verify through new manager instance
        new_manager = ConfigManager(f.name)
        assert new_manager.config["tmdb"]["api_key"] == "new_key"
    
    Path(f.name).unlink(missing_ok=True)

def test_invalid_json_config():
    """Test handling invalid JSON configuration."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"invalid json")
        f.flush()
        
        manager = ConfigManager(f.name)
        assert isinstance(manager.config, dict)
        for section in DEFAULT_CONFIG:
            assert section in manager.config
    
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
        config["telegram"]["bot_token"] = "test_token"
        json.dump(config, f)
        f.flush()
        
        manager = ConfigManager(f.name)
        assert manager.config["notification"]["bot_token"] == manager.config["telegram"]["bot_token"]
        assert manager.config["notification"]["chat_id"] == manager.config["telegram"]["chat_id"]
    
    Path(f.name).unlink(missing_ok=True)

def test_config_creation_error():
    """Test error handling during config creation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Try to create config in non-existent subdirectory
        config_path = os.path.join(temp_dir, "nonexistent", "config.json")
        manager = ConfigManager(config_path)
        
        # Should use default config when creation fails
        assert isinstance(manager.config, dict)
        for section in DEFAULT_CONFIG:
            assert section in manager.config