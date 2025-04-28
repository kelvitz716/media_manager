"""Configuration management."""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "paths": {
        "telegram_download_dir": "downloads",
        "movies_dir": "media/movies",
        "tv_shows_dir": "media/tv_shows",
        "unmatched_dir": "media/unmatched"
    },
    "tmdb": {
        "api_key": ""
    },
    "telegram": {
        "api_id": "",
        "api_hash": "",
        "bot_token": "",
        "enabled": True,
        "chat_id": "",
        "flood_sleep_threshold": 60
    },
    "logging": {
        "level": "INFO",
        "max_size_mb": 10,
        "backup_count": 5
    },
    "download": {
        "chunk_size": 1048576,
        "progress_update_interval": 5,
        "max_retries": 3,
        "retry_delay": 5,
        "max_concurrent_downloads": 3,
        "verify_downloads": True
    },
    "notification": {
        "enabled": True,
        "method": "telegram",
        "bot_token": "",
        "chat_id": ""
    }
}

class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to config file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self._sync_notification_config()
        self._apply_env_overrides()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file.
        
        Returns:
            Configuration dictionary
        """
        config = DEFAULT_CONFIG.copy()
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    self._merge_config(config, file_config)
                    logger.info("Configuration loaded from %s", self.config_path)
            else:
                logger.warning("Config file not found at %s, using defaults", self.config_path)
                self._ensure_config_dir()
                self.save()
        except json.JSONDecodeError:
            logger.error("Invalid JSON in config file %s, using defaults", self.config_path)
        except Exception as e:
            logger.error("Error loading config: %s", e)
            
        return config

    def _merge_config(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Recursively merge configuration dictionaries.
        
        Args:
            base: Base configuration
            update: Update configuration
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        config_dir = os.path.dirname(self.config_path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

    def _sync_notification_config(self) -> None:
        """Synchronize notification and telegram settings."""
        # Sync telegram bot token and chat ID to notification settings
        if self.config["telegram"]["bot_token"]:
            self.config["notification"]["bot_token"] = self.config["telegram"]["bot_token"]
        if self.config["telegram"]["chat_id"]:
            self.config["notification"]["chat_id"] = self.config["telegram"]["chat_id"]

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        env_mapping = {
            "TELEGRAM_API_ID": ("telegram", "api_id"),
            "TELEGRAM_API_HASH": ("telegram", "api_hash"),
            "TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
            "TELEGRAM_CHAT_ID": ("telegram", "chat_id"),
            "TMDB_API_KEY": ("tmdb", "api_key"),
            "LOG_LEVEL": ("logging", "level")
        }
        
        for env_var, (section, key) in env_mapping.items():
            if env_var in os.environ:
                self.config[section][key] = os.environ[env_var]
                if section == "telegram" and key in ["bot_token", "chat_id"]:
                    self._sync_notification_config()

    def save(self) -> None:
        """Save configuration to file."""
        try:
            self._ensure_config_dir()
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Configuration saved to %s", self.config_path)
        except Exception as e:
            logger.error("Error saving config: %s", e)

    def __getitem__(self, key: str) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            
        Returns:
            Configuration value
        """
        return self.config[key]