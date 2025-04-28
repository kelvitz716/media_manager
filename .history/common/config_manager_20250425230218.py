#!/usr/bin/env python3
"""
config_manager.py - Manages loading, validation, and access to the application's configuration.

Reads configuration from a JSON file, validates it against defaults,
and provides easy access to settings.
"""

import os
import json
import logging
import copy
from typing import Dict, Any

# Get a logger instance (assuming logger_setup has configured the root logger)
logger = logging.getLogger(__name__)

# --- Combined Default Configuration ---
# Merges defaults from both original scripts
DEFAULT_CONFIG = {
    "telegram": {
        "api_id": "YOUR_API_ID",         # MUST be filled by user
        "api_hash": "YOUR_API_HASH",     # MUST be filled by user
        "bot_token": "YOUR_BOT_TOKEN",   # MUST be filled by user
        "chat_id": "YOUR_CHAT_ID",       # MUST be filled by user (for notifications/commands)
        "enabled": True,                 # Enable/disable Telegram downloader part
        "flood_sleep_threshold": 60      # From original config.json
    },
    "paths": {
        "telegram_download_dir": "downloads", # Default relative path
        "movies_dir": "media/Movies",         # Default relative path
        "tv_shows_dir": "media/TV Shows",     # Default relative path
        "unmatched_dir": "media/Unmatched",   # Default relative path
        "temp_download_dir": "temp_downloads" # From downloader
    },
    "tmdb": {
        "api_key": "YOUR_TMDB_API_KEY"    # MUST be filled by user
    },
    "logging": {
        "level": "INFO",
        "max_size_mb": 10,
        "backup_count": 5,
        "log_file": "media_manager.log" # Central log file name
    },
    "download": { # Settings for telegram_downloader
        "chunk_size": 1024 * 1024,  # 1MB
        "progress_update_interval": 5,  # seconds
        "max_retries": 3,
        "retry_delay": 5,           # seconds
        "max_concurrent_downloads": 3,
        "verify_downloads": True,
        "max_speed_mbps": 0,        # 0 = unlimited
        "resume_support": True,
    },
    "watcher": { # Settings specific to file_watcher
        "process_existing_files": True,
        "max_worker_threads": 3,
        "lock_timeout_minutes": 60,
        "file_stabilization_seconds": 5, # Slightly longer default
        "manual_categorization": {
            "session_timeout_seconds": 300,  # 5 minutes
            "media_types": ["movie", "tv_show", "anime", "documentary", "other"]
        }
    },
    "notification": { # Settings for notification_service
        "enabled": True,
        "method": "telegram",  # Options: "print", "telegram"
        # Telegram settings are taken from the main "telegram" section above
    }
}

class ConfigManager:
    """Manages loading, validation, and access to configuration."""

    def __init__(self, config_path: str = "config.json"):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to the configuration file.
        """
        self.config_path = config_path
        self.config = self._load_or_create_config()
        self._validate_config() # Validate and apply defaults after loading

    def _load_or_create_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or create default if it doesn't exist.

        Returns:
            Configuration dictionary.
        """
        if not os.path.exists(self.config_path):
            logger.warning(f"Configuration file not found at {self.config_path}. Creating default.")
            print(f"Configuration file not found at {self.config_path}. Creating default.")
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(self.config_path)) or '.', exist_ok=True)
                # Write default config
                with open(self.config_path, 'w') as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4)
                logger.info(f"Default configuration file created at {self.config_path}")
                print("\n" + "="*60)
                print("IMPORTANT: Please edit config.json with your details:")
                print("  - Telegram API ID, API Hash, Bot Token, Chat ID")
                print("  - TMDb API Key")
                print("  - Review directory paths")
                print("="*60 + "\n")
                return copy.deepcopy(DEFAULT_CONFIG) # Return a copy
            except IOError as e:
                logger.error(f"Failed to create configuration file {self.config_path}: {e}")
                print(f"ERROR: Failed to create configuration file {self.config_path}: {e}")
                # Return default config in memory as fallback
                return copy.deepcopy(DEFAULT_CONFIG)

        try:
            with open(self.config_path, 'r') as f:
                user_config = json.load(f)
                logger.info(f"Loaded configuration from {self.config_path}")
                return user_config
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.config_path}: {e}. Using default config.")
            print(f"ERROR: Invalid JSON in {self.config_path}. Please fix or delete the file.")
            return copy.deepcopy(DEFAULT_CONFIG) # Return default if file is invalid
        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_path}: {e}. Using default config.")
            return copy.deepcopy(DEFAULT_CONFIG) # Return default on other errors

    def _validate_config(self) -> None:
        """
        Validate configuration and recursively apply defaults for missing values.
        Saves the updated config if changes were made.
        """
        updated = False
        validated_config = copy.deepcopy(DEFAULT_CONFIG)

        def merge_dicts(default: Dict, user: Dict) -> bool:
            """Recursively merge user config into default config."""
            changed = False
            for key, default_value in default.items():
                if key not in user:
                    user[key] = default_value # Add missing key from default
                    nonlocal updated
                    updated = True
                    changed = True
                    logger.debug(f"Applying default for missing config key: {key}")
                elif isinstance(default_value, dict) and isinstance(user.get(key), dict):
                    # Recursively merge sub-dictionaries
                    if merge_dicts(default_value, user[key]):
                        changed = True
                # You could add type checking here if needed
                # elif type(default_value) != type(user.get(key)):
                #    logger.warning(f"Config type mismatch for key '{key}'. Expected {type(default_value)}, got {type(user.get(key))}. Using default.")
                #    user[key] = default_value
                #    nonlocal updated
                #    updated = True
                #    changed = True
            return changed

        # Start the merge process
        merge_dicts(validated_config, self.config)

        # Check for essential user-provided values
        essential_keys = [
            ("telegram", "api_id", "YOUR_API_ID"),
            ("telegram", "api_hash", "YOUR_API_HASH"),
            ("telegram", "bot_token", "YOUR_BOT_TOKEN"),
            ("telegram", "chat_id", "YOUR_CHAT_ID"),
            ("tmdb", "api_key", "YOUR_TMDB_API_KEY"),
        ]
        missing_essentials = False
        for section, key, placeholder in essential_keys:
             if self.config.get(section, {}).get(key) == placeholder or not self.config.get(section, {}).get(key):
                 logger.warning(f"Essential configuration value '{section}.{key}' is missing or uses placeholder.")
                 print(f"WARNING: Essential configuration value '{section}.{key}' MUST be set in {self.config_path}")
                 missing_essentials = True

        if missing_essentials:
             print(f"WARNING: Please update {self.config_path} with your API keys and IDs.")


        # Ensure notification settings use the main telegram details if method is telegram
        if self.config.get("notification", {}).get("method") == "telegram":
             if "telegram" not in self.config.get("notification", {}):
                 self.config["notification"]["telegram"] = {} # Ensure section exists

             # Copy essential details from main telegram section if needed
             for key in ["bot_token", "chat_id"]:
                 if self.config["notification"]["telegram"].get(key) != self.config["telegram"].get(key):
                     self.config["notification"]["telegram"][key] = self.config["telegram"].get(key)
                     logger.debug(f"Updating notification.telegram.{key} from main telegram config.")
                     updated = True


        if updated:
            logger.info("Configuration updated with default values. Saving.")
            self.save() # Save the config if defaults were applied

    def save(self) -> None:
        """Save the current configuration back to the file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4, sort_keys=True)
            logger.debug(f"Configuration saved to {self.config_path}")
        except IOError as e:
            logger.error(f"Failed to save configuration to {self.config_path}: {e}")
            print(f"ERROR: Could not save configuration to {self.config_path}")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Safely get a configuration value with section/key structure.

        Args:
            section: The top-level configuration section (e.g., "paths").
            key: The key within the section (e.g., "movies_dir").
            default: The value to return if the section or key is not found.

        Returns:
            The configuration value or the default.
        """
        return self.config.get(section, {}).get(key, default)

    def __getitem__(self, key: str) -> Dict:
        """
        Allow dictionary-style access to configuration sections.
        Example: config_manager['paths']

        Args:
            key: The top-level section key.

        Returns:
            The dictionary representing the configuration section, or empty dict if not found.
        """
        return self.config.get(key, {})

# Example usage (optional, for testing)
if __name__ == "__main__":
    print("Testing ConfigManager...")
    # Assuming config.json is in the same directory or created
    manager = ConfigManager("test_config.json")
    print("\nLoaded/Created Config:")
    print(json.dumps(manager.config, indent=2))

    # Example access
    log_level = manager.get("logging", "level", "WARNING")
    movies_path = manager["paths"].get("movies_dir")
    print(f"\nLog Level: {log_level}")
    print(f"Movies Path: {movies_path}")

    # Clean up test file
    # try:
    #     os.remove("test_config.json")
    #     print("\nCleaned up test_config.json")
    # except OSError:
    #     pass
