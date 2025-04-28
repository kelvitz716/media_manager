"""Configuration management module."""
import json
import os
from typing import Dict, Any
from dotenv import load_dotenv

class ConfigManager:
    """Manages configuration loading, validation and access."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize configuration manager."""
        # Load environment variables
        load_dotenv()
        
        self.config_path = config_path
        self.config = self._load_or_create_config()
        self._validate_config()
        self._override_from_env()
        
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            print(f"Created default configuration file at {self.config_path}")
            return DEFAULT_CONFIG.copy()
        
        with open(self.config_path, 'r') as f:
            return json.load(f)
            
    def _override_from_env(self) -> None:
        """Override configuration values from environment variables."""
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
        if max_speed := os.getenv("MAX_SPEED_MBPS"):
            speed = float(max_speed)
            self.config["download"]["max_speed_mbps"] = speed if speed > 0 else None
            
    def _validate_config(self) -> None:
        """Validate configuration and set defaults."""
        required_sections = {
            "paths": ["telegram_download_dir", "movies_dir", "tv_shows_dir", "unmatched_dir"],
            "telegram": ["api_id", "api_hash", "bot_token", "enabled"],
            "logging": ["level", "max_size_mb", "backup_count"],
            "download": ["chunk_size", "progress_update_interval", "max_retries", 
                        "retry_delay", "max_concurrent_downloads", "verify_downloads"]
        }
        
        for section, keys in required_sections.items():
            if section not in self.config:
                self.config[section] = {}
            for key in keys:
                if key not in self.config[section]:
                    self.config[section][key] = DEFAULT_CONFIG[section][key]
                    
        self.save()
                
    def save(self) -> None:
        """Save current configuration to file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
            
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Safely get configuration value with default fallback."""
        return self.config.get(section, {}).get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Get configuration section by key."""
        return self.config.get(key, {})

# Default configuration
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
        "chunk_size": 1024 * 1024,  # 1MB
        "progress_update_interval": 5,
        "max_retries": 3,
        "retry_delay": 5,
        "max_concurrent_downloads": 3,
        "verify_downloads": True,
        "temp_download_dir": "temp_downloads",
        "max_speed_mbps": None
    },
    "notification": {
        "enabled": True,
        "method": "telegram",
        "bot_token": "YOUR_BOT_TOKEN",
        "chat_id": ""
    },
    "process_existing_files": True
}