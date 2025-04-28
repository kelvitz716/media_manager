"""Configuration management module."""
import json
import os
from typing import Dict, Any

class ConfigManager:
    """Manages configuration loading, validation and access."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_or_create_config()
        self._validate_config()
        
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            print(f"Created default configuration file at {self.config_path}")
            return DEFAULT_CONFIG
        
        with open(self.config_path, 'r') as f:
            return json.load(f)
            
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
        "telegram_download_dir": "telegram_download_dir",
        "movies_dir": "movies_dir",
        "tv_shows_dir": "tv_shows_dir",
        "unmatched_dir": "unmatched_dir"
    },
    "tmdb": {
        "api_key": "api_key"
    },
    "telegram": {
        "api_id": "api_id",
        "api_hash": "api_hash",
        "bot_token": "bot_token",
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
        "temp_download_dir": "temp_downloads"
    },
    "notification": {
        "enabled": True,
        "method": "telegram"
    },
    "process_existing_files": True
}