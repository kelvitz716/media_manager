"""Configuration management module."""
import json
import os
import logging
from typing import Dict, Any

class ConfigManager:
    """Manages configuration loading and access."""
    
    def __init__(self, config_path: str):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to the configuration file
        """
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self.config = self._load_config()
        self._load_secrets()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file: {e}")
            raise
            
    def _load_secrets(self) -> None:
        """Load secrets from Docker secrets or environment variables."""
        # Define secret mappings
        secret_mappings = {
            "tmdb": {
                "api_key": ("TMDB_API_KEY", "tmdb_api_key")
            },
            "telegram": {
                "api_id": ("TELEGRAM_API_ID", "telegram_api_id"),
                "api_hash": ("TELEGRAM_API_HASH", "telegram_api_hash"),
                "bot_token": ("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
                "chat_id": ("TELEGRAM_CHAT_ID", "telegram_chat_id")
            }
        }
        
        # Update config with secrets
        for section, secrets in secret_mappings.items():
            for config_key, (env_key, secret_file) in secrets.items():
                value = None
                
                # Try Docker secret first
                secret_path = f"/run/secrets/{secret_file}"
                if os.path.exists(secret_path):
                    with open(secret_path, 'r') as f:
                        value = f.read().strip()
                        self.logger.debug(f"Loaded {config_key} from Docker secret")
                
                # Fall back to environment variable
                if not value and env_key in os.environ:
                    value = os.environ[env_key]
                    self.logger.debug(f"Loaded {config_key} from environment")
                
                # Update config if value was found
                if value:
                    self.config[section][config_key] = value
                    # Log only first/last 4 chars of sensitive data
                    safe_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
                    self.logger.info(f"Configured {section}.{config_key}: {safe_value}")
                else:
                    self.logger.warning(f"No value found for {section}.{config_key}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return self.config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Get configuration value using dictionary access."""
        return self.config[key]