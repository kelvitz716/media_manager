#!/bin/bash

# Function to substitute environment variables in config file
envsubst_config() {
    local config_file="$1"
    local temp_file="${config_file}.tmp"
    
    # Create a backup of original config
    cp "$config_file" "${config_file}.bak"
    
    # Replace environment variables in config
    envsubst < "$config_file" > "$temp_file"
    mv "$temp_file" "$config_file"
}

# Ensure config.json exists and has proper permissions
if [ ! -f "/app/config.json" ]; then
    echo "Error: config.json not found!"
    exit 1
fi

# Substitute environment variables in config.json
envsubst_config "/app/config.json"

# Start the application
exec python -m media_manager.main