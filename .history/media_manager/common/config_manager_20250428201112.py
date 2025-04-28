"""Configuration management."""
import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "telegram": {
        "api_id": "YOUR_API_ID",
        "api_hash": "YOUR_API_HASH",
        "bot_token": "YOUR_BOT_TOKEN",
        "chat_id": "YOUR_CHAT_ID",
        "enabled": True,
        "flood_sleep_threshold": 60
    },
    "downloader": {
        "bot_token": "",  # Will be synced from telegram section
        "api_id": "",    # Will be synced from telegram section
        "api_hash": "",  # Will be synced from telegram section
        "chat_id": ""    # Will be synced from telegram section
    },
    "download": {
        "max_concurrent_downloads": 3,
        "speed_limit": 0,  # 0 = unlimited
        "chunk_size": 1024 * 1024  # 1MB
    },
    "paths": {
        "telegram_download_dir": "downloads",
        "temp_download_dir": "temp_downloads"
    },
    "notification": {
        "enabled": True,
        "method": "telegram",
        "bot_token": "",  # Will be synced from telegram section
        "chat_id": ""    # Will be synced from telegram section
    }
}

class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: str):
        """Initialize configuration manager."""
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
        self._sync_credentials()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            print(f"Created default configuration at {self.config_path}")
            print("Please edit this file with your Telegram API credentials")
            return DEFAULT_CONFIG

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _validate_config(self) -> None:
        """Validate configuration and set defaults."""
        # Ensure all sections exist
        for section in DEFAULT_CONFIG:
            if section not in self.config:
                self.config[section] = DEFAULT_CONFIG[section].copy()

        # Validate telegram settings
        self._validate_telegram()
        self._validate_paths()
        self._validate_download()
        self._validate_notification()
        
        # Save validated config
        self._save_config()

    def _validate_telegram(self) -> None:
        """Validate Telegram configuration."""
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

    def _validate_paths(self) -> None:
        """Validate paths configuration."""
        paths_config = self.config["paths"]
        defaults = DEFAULT_CONFIG["paths"]
        
        for path in defaults:
            if path not in paths_config:
                paths_config[path] = defaults[path]

    def _validate_download(self) -> None:
        """Validate download configuration."""
        download_config = self.config["download"]
        defaults = DEFAULT_CONFIG["download"]
        
        for key in defaults:
            if key not in download_config:
                download_config[key] = defaults[key]

    def _validate_notification(self) -> None:
        """Validate notification configuration."""
        notification_config = self.config["notification"]
        defaults = DEFAULT_CONFIG["notification"]
        
        if not isinstance(notification_config.get("enabled"), bool):
            notification_config["enabled"] = defaults["enabled"]
            
        if "method" not in notification_config:
            notification_config["method"] = defaults["method"]

    def _sync_credentials(self) -> None:
        """Synchronize credentials across sections."""
        # Sync from telegram section to notification
        if self.config["telegram"]["bot_token"]:
            self.config["notification"]["bot_token"] = self.config["telegram"]["bot_token"]
        if self.config["telegram"]["chat_id"]:
            self.config["notification"]["chat_id"] = self.config["telegram"]["chat_id"]

        # Sync from telegram section to downloader
        for key in ["bot_token", "api_id", "api_hash", "chat_id"]:
            if self.config["telegram"].get(key):
                self.config["downloader"][key] = self.config["telegram"][key]

        # Save synced config
        self._save_config()

    def _save_config(self) -> None:
        """Save current configuration to file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def __getitem__(self, key: str) -> Any:
        """Get configuration section."""
        return self.config[key]