#!/bin/bash

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please run init_config.py first."
    exit 1
fi

# Create .secrets directory if it doesn't exist
mkdir -p .secrets

# Process each line in .env file
while IFS='=' read -r key value; do
    # Skip empty lines or lines starting with #
    if [ -z "$key" ] || [[ $key == \#* ]]; then
        continue
    fi
    
    # Convert to lowercase for file naming
    secret_file=".secrets/${key,,}.txt"
    
    # Save value to secret file
    echo -n "$value" > "$secret_file"
    echo "Created secret file: $secret_file"
done < .env

echo "Docker secrets have been created successfully!"