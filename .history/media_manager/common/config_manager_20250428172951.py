"""Configuration management."""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

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
        self._validate_config()
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

    def _validate_config(self) -> None:
        """Validate configuration values."""
        self._validate_paths()
        self._validate_logging()
        self._validate_telegram()
        self._validate_notification()
        self._validate_download()

    def _validate_paths(self) -> None:
        """Validate path configuration."""
        required_paths = [
            "telegram_download_dir",
            "movies_dir",
            "tv_shows_dir",
            "unmatched_dir"
        ]
        for path in required_paths:
            if not self.config["paths"].get(path):
                self.config["paths"][path] = DEFAULT_CONFIG["paths"][path]

    def _validate_logging(self) -> None:
        """Validate logging configuration."""
        if "logging" not in self.config:
            self.config["logging"] = DEFAULT_CONFIG["logging"]
        else:
            logging_config = self.config["logging"]
            defaults = DEFAULT_CONFIG["logging"]
            
            if not isinstance(logging_config.get("level"), str):
                logging_config["level"] = defaults["level"]
            if not isinstance(logging_config.get("max_size_mb"), (int, float)):
                logging_config["max_size_mb"] = defaults["max_size_mb"]
            if not isinstance(logging_config.get("backup_count"), int):
                logging_config["backup_count"] = defaults["backup_count"]

    def _validate_telegram(self) -> None:
        """Validate Telegram configuration."""
        if "telegram" not in self.config:
            self.config["telegram"] = DEFAULT_CONFIG["telegram"]
        else:
            telegram_config = self.config["telegram"]
            defaults = DEFAULT_CONFIG["telegram"]
            
            # Ensure required fields exist with proper types
            if not isinstance(telegram_config.get("enabled"), bool):
                telegram_config["enabled"] = defaults["enabled"]
            if not isinstance(telegram_config.get("flood_sleep_threshold"), int):
                telegram_config["flood_sleep_threshold"] = defaults["flood_sleep_threshold"]
            
            # Ensure API credentials are strings
            for field in ["api_id", "api_hash", "bot_token", "chat_id"]:
                if not isinstance(telegram_config.get(field), str):
                    telegram_config[field] = defaults[field]

    def _validate_notification(self) -> None:
        """Validate notification configuration."""
        if "notification" not in self.config:
            self.config["notification"] = DEFAULT_CONFIG["notification"]
        else:
            notification_config = self.config["notification"]
            defaults = DEFAULT_CONFIG["notification"]
            
            if not isinstance(notification_config.get("enabled"), bool):
                notification_config["enabled"] = defaults["enabled"]
            if not isinstance(notification_config.get("method"), str):
                notification_config["method"] = defaults["method"]
            if not isinstance(notification_config.get("bot_token"), str):
                notification_config["bot_token"] = defaults["bot_token"]
            if not isinstance(notification_config.get("chat_id"), str):
                notification_config["chat_id"] = defaults["chat_id"]

    def _validate_download(self) -> None:
        """Validate download configuration."""
        if "download" not in self.config:
            self.config["download"] = DEFAULT_CONFIG["download"]
        else:
            download_config = self.config["download"]
            defaults = DEFAULT_CONFIG["download"]
            
            # Validate numeric fields
            for field in ["chunk_size", "progress_update_interval", "max_retries", 
                         "retry_delay", "max_concurrent_downloads"]:
                if not isinstance(download_config.get(field), (int, type(None))):
                    download_config[field] = defaults[field]
            
            # Validate boolean fields
            if not isinstance(download_config.get("verify_downloads"), bool):
                download_config["verify_downloads"] = defaults["verify_downloads"]

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