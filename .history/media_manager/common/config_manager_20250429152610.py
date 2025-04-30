"""Configuration management module."""
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "paths": {
        "telegram_download_dir": "downloads",
        "movies_dir": "media/movies",
        "tv_shows_dir": "media/tv_shows",
        "unmatched_dir": "media/unmatched",
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

    def get(self, section: str, default: Any = None) -> Any:
        """Get a configuration section with default fallback.
        
        Args:
            section: Name of the configuration section
            default: Default value if section doesn't exist
            
        Returns:
            Configuration section or default value
        """
        return self.config.get(section, default)

    def _resolve_secrets(self) -> None:
        """Resolve secrets from environment variables."""
        for section in self.config:
            if isinstance(self.config[section], dict):
                for key, value in self.config[section].items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var = value[2:-1]
                        self.config[section][key] = os.environ.get(env_var, value)

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
        if "telegram" not in self.config:
            self.config["telegram"] = {}
        
        telegram_config = self.config["telegram"]
        defaults = DEFAULT_CONFIG.get("telegram", {})
        
        # Ensure required fields exist
        for key in ["bot_token", "chat_id"]:
            if key not in telegram_config:
                telegram_config[key] = defaults.get(key, "")

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
        if "download" not in self.config:
            self.config["download"] = {}

        download_config = self.config["download"]
        defaults = {
            "chunk_size": 1024 * 1024,  # 1MB
            "progress_update_interval": 5,
            "max_retries": 3,
            "retry_delay": 5,
            "max_concurrent_downloads": 3,
            "verify_downloads": True
        }

        for key, value in defaults.items():
            if key not in download_config:
                download_config[key] = value

    def _validate_notification(self) -> None:
        """Validate notification configuration."""
        if "notification" not in self.config:
            self.config["notification"] = DEFAULT_CONFIG["notification"].copy()

    def _validate_tmdb(self) -> None:
        """Validate TMDB configuration."""
        if "tmdb" not in self.config:
            self.config["tmdb"] = DEFAULT_CONFIG["tmdb"].copy()

    def _sync_credentials(self) -> None:
        """Synchronize credentials across sections."""
        # Sync notification settings with telegram if needed
        if (self.config.get("notification", {}).get("method") == "telegram" and
            "telegram" in self.config):
            # Copy essential details from telegram section
            for key in ["bot_token", "chat_id"]:
                if key in self.config["telegram"]:
                    self.config["notification"][key] = self.config["telegram"][key]

    def _save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.debug("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {e}")