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
    "telegram": {
        "enabled": True,
        "bot_token": "${TELEGRAM_BOT_TOKEN}",
        "api_id": "${TELEGRAM_API_ID}",
        "api_hash": "${TELEGRAM_API_HASH}",
        "chat_id": "${TELEGRAM_CHAT_ID}",
        "flood_sleep_threshold": 60
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
        """Resolve secrets from environment variables and Docker secrets."""
        def read_secret(secret_name: str) -> Optional[str]:
            """Read a secret from Docker secrets or environment variable."""
            # First try Docker secrets
            secret_path = f"/run/secrets/{secret_name.lower()}"
            if os.path.exists(secret_path):
                try:
                    with open(secret_path, 'r') as f:
                        return f.read().strip()
                except Exception as e:
                    logger.warning(f"Error reading secret {secret_name}: {e}")
            
            # Fallback to environment variable
            return os.environ.get(secret_name)

        for section in self.config:
            if isinstance(self.config[section], dict):
                for key, value in self.config[section].items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var = value[2:-1]
                        secret_value = read_secret(env_var)
                        if secret_value:
                            self.config[section][key] = secret_value
                        else:
                            logger.warning(f"Could not resolve secret for {env_var}")

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
            self.config["telegram"] = DEFAULT_CONFIG["telegram"].copy()
            logger.debug("Added missing telegram section")
        
        telegram_config = self.config["telegram"]
        defaults = DEFAULT_CONFIG["telegram"]
        
        # Ensure all required fields exist with defaults
        for key, default_value in defaults.items():
            if key not in telegram_config:
                telegram_config[key] = default_value
                logger.debug(f"Added missing telegram setting: {key}")

        # Ensure notification section has the same credentials
        if "notification" in self.config:
            self.config["notification"]["bot_token"] = telegram_config["bot_token"]
            self.config["notification"]["chat_id"] = telegram_config["chat_id"]

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
        # Create downloader section if it doesn't exist
        if "downloader" not in self.config:
            self.config["downloader"] = {}
            logger.debug("Created missing downloader section")

        # Sync from telegram section to downloader
        for key in ["bot_token", "api_id", "api_hash", "chat_id"]:
            if self.config["telegram"].get(key):
                self.config["downloader"][key] = self.config["telegram"][key]
                # Mask sensitive data in logs
                masked_value = '****' if key != 'chat_id' else self.config["telegram"][key]
                logger.debug(f"Synced {key} from telegram to downloader section: {masked_value}")
            else:
                logger.warning(f"Missing {key} in telegram section")

        # Only sync chat_id from telegram to notification if notification section exists
        if "notification" in self.config and self.config["telegram"].get("chat_id"):
            self.config["notification"]["chat_id"] = self.config["telegram"]["chat_id"]
            logger.debug(f"Synced chat_id to notification section: {self.config['telegram']['chat_id']}")

        # Log the final state of the token
        if "bot_token" in self.config["telegram"]:
            token = self.config["telegram"]["bot_token"]
            # Only log first 3 chars and presence of colon for security
            prefix = token[:3] if len(token) > 3 else token
            has_colon = ':' in token
            logger.debug(f"Final bot_token state - prefix: {prefix}..., contains colon: {has_colon}")

    def _save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.debug("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {e}")