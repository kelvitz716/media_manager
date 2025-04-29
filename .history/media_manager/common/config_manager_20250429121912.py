"""Configuration management."""
import os
import json
import logging
from typing import Dict, Any
from .secrets_manager import get_secret, get_required_secret

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "telegram": {
        "api_id": "${TELEGRAM_API_ID}",
        "api_hash": "${TELEGRAM_API_HASH}",
        "bot_token": "${TELEGRAM_BOT_TOKEN}",
        "chat_id": "${TELEGRAM_CHAT_ID}",
        "enabled": True,
        "flood_sleep_threshold": 60
    },
    "downloader": {
        "bot_token": "${TELEGRAM_BOT_TOKEN}",
        "api_id": "${TELEGRAM_API_ID}",
        "api_hash": "${TELEGRAM_API_HASH}",
        "chat_id": "${TELEGRAM_CHAT_ID}"
    },
    "download": {
        "max_concurrent_downloads": 3,
        "speed_limit": 0,
        "chunk_size": 1024 * 1024
    },
    "paths": {
        "telegram_download_dir": "downloads",
        "temp_download_dir": "temp_downloads"
    },
    "notification": {
        "enabled": True,
        "method": "telegram",
        "bot_token": "${TELEGRAM_BOT_TOKEN}",
        "chat_id": "${TELEGRAM_CHAT_ID}"
    },
    "logging": {
        "level": "INFO",
        "max_size_mb": 10,
        "backup_count": 5,
        "log_file": "media_watcher.log",
        "log_dir": "logs"
    },
    "tmdb": {
        "api_key": "${TMDB_API_KEY}",
        "language": "en-US",
        "include_adult": False
    }
}

class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: str):
        """Initialize configuration manager."""
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
        self._resolve_secrets()
        self._sync_credentials()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            logger.info(f"Created default configuration file at {self.config_path}")
            return DEFAULT_CONFIG.copy()

        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.debug("Successfully loaded configuration file")
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return DEFAULT_CONFIG.copy()

    def _resolve_secrets(self) -> None:
        """Resolve secrets from environment variables or Docker secrets."""
        try:
            # Resolve Telegram secrets
            self.config["telegram"]["api_id"] = get_required_secret("TELEGRAM_API_ID")
            self.config["telegram"]["api_hash"] = get_required_secret("TELEGRAM_API_HASH")
            self.config["telegram"]["bot_token"] = get_required_secret("TELEGRAM_BOT_TOKEN")
            self.config["telegram"]["chat_id"] = get_required_secret("TELEGRAM_CHAT_ID")

            # Resolve TMDB secrets
            self.config["tmdb"]["api_key"] = get_required_secret("TMDB_API_KEY")

            logger.debug("Successfully resolved all secrets")
        except ValueError as e:
            logger.error(f"Error resolving secrets: {e}")
            raise

    def _validate_config(self) -> None:
        """Validate configuration and set defaults."""
        # Ensure all sections exist
        for section in DEFAULT_CONFIG:
            if section not in self.config:
                self.config[section] = DEFAULT_CONFIG[section].copy()
                logger.debug(f"Added missing section: {section}")

        # Validate all sections
        self._validate_telegram()
        self._validate_paths()
        self._validate_download()
        self._validate_notification()
        self._validate_tmdb()
        
        # Save validated config
        self._save_config()

    def _validate_telegram(self) -> None:
        """Validate Telegram configuration."""
        telegram_config = self.config["telegram"]
        defaults = DEFAULT_CONFIG["telegram"]
        
        # Validate boolean and numeric settings
        if not isinstance(telegram_config.get("enabled"), bool):
            telegram_config["enabled"] = defaults["enabled"]
            
        if not isinstance(telegram_config.get("flood_sleep_threshold"), int):
            telegram_config["flood_sleep_threshold"] = defaults["flood_sleep_threshold"]

    def _validate_paths(self) -> None:
        """Validate paths configuration."""
        paths_config = self.config["paths"]
        defaults = DEFAULT_CONFIG["paths"]
        
        # Ensure all path settings exist
        for path in defaults:
            if path not in paths_config:
                paths_config[path] = defaults[path]
                logger.debug(f"Added missing path setting: {path}")
            
        # Convert relative paths to absolute
        base_dir = os.path.dirname(os.path.abspath(self.config_path))
        for key, path in paths_config.items():
            if not os.path.isabs(path):
                paths_config[key] = os.path.join(base_dir, path)

    def _validate_download(self) -> None:
        """Validate download configuration."""
        download_config = self.config["download"]
        defaults = DEFAULT_CONFIG["download"]
        
        # Validate numeric settings
        for key in ["max_concurrent_downloads", "speed_limit", "chunk_size"]:
            if key not in download_config or not isinstance(download_config[key], (int, float)):
                download_config[key] = defaults[key]

    def _validate_notification(self) -> None:
        """Validate notification configuration."""
        notification_config = self.config["notification"]
        defaults = DEFAULT_CONFIG["notification"]
        
        if not isinstance(notification_config.get("enabled"), bool):
            notification_config["enabled"] = defaults["enabled"]
            
        if "method" not in notification_config:
            notification_config["method"] = defaults["method"]

    def _validate_tmdb(self) -> None:
        """Validate TMDB configuration."""
        if "tmdb" not in self.config:
            self.config["tmdb"] = DEFAULT_CONFIG["tmdb"].copy()
            logger.debug("Added missing TMDB configuration section")
            return
            
        tmdb_config = self.config["tmdb"]
        defaults = DEFAULT_CONFIG["tmdb"]
            
        # Validate language
        if not isinstance(tmdb_config.get("language"), str):
            tmdb_config["language"] = defaults["language"]
            
        # Validate include_adult setting
        if not isinstance(tmdb_config.get("include_adult"), bool):
            tmdb_config["include_adult"] = defaults["include_adult"]

    def _sync_credentials(self) -> None:
        """Synchronize credentials across sections."""
        # Sync from telegram section to downloader
        for key in ["bot_token", "api_id", "api_hash", "chat_id"]:
            self.config["downloader"][key] = self.config["telegram"][key]

        # Sync chat_id and bot_token to notification
        self.config["notification"]["chat_id"] = self.config["telegram"]["chat_id"]
        self.config["notification"]["bot_token"] = self.config["telegram"]["bot_token"]

    def _save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.debug("Successfully saved configuration")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def __getitem__(self, key: str) -> Any:
        """Get configuration section."""
        return self.config[key]