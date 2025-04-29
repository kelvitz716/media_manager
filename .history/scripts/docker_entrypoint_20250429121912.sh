#!/bin/bash

# Function to substitute environment variables in config file
envsubst_config() {
    local config_file="$1"
    local temp_dir="/tmp/media_manager"
    local temp_file="${temp_dir}/config.json.tmp"
    
    # Create temp directory
    mkdir -p "$temp_dir"
    
    # Create a backup of original config in temp directory
    cp "$config_file" "${temp_dir}/config.json.bak"
    
    # Replace environment variables in config using temp directory
    envsubst < "$config_file" > "$temp_file"
    cp "$temp_file" "$config_file"
    rm -f "$temp_file"
}

# Ensure config.json exists and has proper permissions
if [ ! -f "/app/config.json" ]; then
    echo "Error: config.json not found!"
    exit 1
fi

# Ensure config file is writable
chmod 644 "/app/config.json"

# Substitute environment variables in config.json
envsubst_config "/app/config.json"

# Start the application
exec python -m media_manager.main