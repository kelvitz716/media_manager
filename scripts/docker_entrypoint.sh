#!/bin/bash

# Function to update config with secrets
update_config() {
    python3 - << 'EOF'
import json
import os

def read_secret(name):
    """Read a secret from the Docker secrets directory."""
    try:
        with open(f"/run/secrets/{name}", "r") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Warning: Could not read secret {name}: {e}")
        return None

# Load the config file
config_file = "/app/config.json"
with open(config_file, "r") as f:
    config = json.load(f)

# Map of secret files to config paths
secret_mappings = {
    "tmdb_api_key": ("tmdb", "api_key"),
    "telegram_api_id": ("telegram", "api_id"),
    "telegram_api_hash": ("telegram", "api_hash"),
    "telegram_bot_token": ("telegram", "bot_token"),
    "telegram_chat_id": ("telegram", "chat_id")
}

# Update config with secrets
for secret_name, (section, key) in secret_mappings.items():
    value = read_secret(secret_name)
    if value:
        # Special handling for numeric values
        if key in ["api_id", "chat_id"]:
            try:
                value = int(value)
            except ValueError:
                print(f"Warning: Could not convert {key} to integer: {value}")
                continue
        
        # Update both in telegram and notification sections if applicable
        config[section][key] = value
        if section == "telegram" and key in ["bot_token", "chat_id"]:
            config["notification"][key] = value

# Save updated config
with open(config_file, "w") as f:
    json.dump(config, f, indent=4)
    
print("Config updated successfully with secrets")
EOF
}

# Ensure config.json exists
if [ ! -f "/app/config.json" ]; then
    echo "Error: config.json not found!"
    exit 1
fi

# Update config with secrets
update_config

# Start the application
exec python -m media_manager.main