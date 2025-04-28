"""Configuration management module."""
import json
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Default configuration with notification section
DEFAULT_CONFIG = {
    "paths": {
        "telegram_download_dir": "downloads",
        "movies_dir": "media/movies",
        "tv_shows_dir": "media/tv_shows",
        "unmatched_dir": "media/unmatched"
    },
    "tmdb": {
        "api_key": "YOUR_TMDB_API_KEY_HERE"
    },
    "telegram": {
        "api_id": "YOUR_TELEGRAM_API_ID",
        "api_hash": "YOUR_TELEGRAM_API_HASH",
        "bot_token": "YOUR_BOT_TOKEN",
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
        "chunk_size": 1024 * 1024,
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
    """Manages configuration loading, validation and access."""
    
    def __init__(self, config_path: str):
        """Initialize configuration manager."""
        self.config_path = config_path
        load_dotenv()  # Load environment variables from .env file
        self.config = self._load_or_create_config()
        self._validate_config()
        self._override_from_env()
        self.save()  # Save any changes made during validation/override
    
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load existing config or create new one with defaults."""
        if not os.path.exists(self.config_path):
            try:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w') as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4)
                return DEFAULT_CONFIG.copy()
            except IOError:
                return DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return DEFAULT_CONFIG.copy()
    
    def _override_from_env(self) -> None:
        """Override configuration values from environment variables."""
        # Initialize notification section if not present
        if "notification" not in self.config:
            self.config["notification"] = DEFAULT_CONFIG["notification"].copy()
            
        # Telegram settings
        if api_id := os.getenv("TELEGRAM_API_ID"):
            self.config["telegram"]["api_id"] = api_id
        if api_hash := os.getenv("TELEGRAM_API_HASH"):
            self.config["telegram"]["api_hash"] = api_hash
        if bot_token := os.getenv("TELEGRAM_BOT_TOKEN"):
            self.config["telegram"]["bot_token"] = bot_token
            self.config["notification"]["bot_token"] = bot_token
        if chat_id := os.getenv("TELEGRAM_CHAT_ID"):
            self.config["telegram"]["chat_id"] = chat_id
            self.config["notification"]["chat_id"] = chat_id
            
        # TMDB settings
        if tmdb_key := os.getenv("TMDB_API_KEY"):
            self.config["tmdb"]["api_key"] = tmdb_key
            
        # Optional settings
        if log_level := os.getenv("LOG_LEVEL"):
            self.config["logging"]["level"] = log_level.upper()
        if max_downloads := os.getenv("MAX_CONCURRENT_DOWNLOADS"):
            self.config["download"]["max_concurrent_downloads"] = int(max_downloads)
    
    def _validate_config(self) -> None:
        """Validate configuration and apply defaults."""
        # Ensure all sections exist
        for section, defaults in DEFAULT_CONFIG.items():
            if section not in self.config:
                self.config[section] = defaults.copy()
            else:
                # Ensure all keys exist in each section
                for key, default_value in defaults.items():
                    if key not in self.config[section]:
                        self.config[section][key] = default_value
                    else:
                        # Type validation and conversion
                        current_value = self.config[section][key]
                        if isinstance(default_value, (int, float)) and isinstance(current_value, str):
                            try:
                                if isinstance(default_value, int):
                                    self.config[section][key] = int(current_value)
                                else:
                                    self.config[section][key] = float(current_value)
                            except ValueError:
                                self.config[section][key] = default_value
                        elif isinstance(default_value, bool) and isinstance(current_value, str):
                            self.config[section][key] = current_value.lower() == 'true'
        
        # Sync notification settings with telegram settings
        if self.config["notification"]["method"] == "telegram":
            self.config["notification"]["bot_token"] = self.config["telegram"]["bot_token"]
            self.config["notification"]["chat_id"] = self.config["telegram"]["chat_id"]
    
    def save(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except IOError:
            pass  # Ignore save errors
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Safely get configuration value with default fallback."""
        return self.config.get(section, {}).get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Get configuration section by key."""
        return self.config.get(key, {})