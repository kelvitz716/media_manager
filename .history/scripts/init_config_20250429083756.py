#!/usr/bin/env python3
"""Configuration initialization script for Media Manager."""
import os
import json
import click
from pathlib import Path

CONFIG_TEMPLATE = {
    "paths": {
        "telegram_download_dir": "",
        "movies_dir": "",
        "tv_shows_dir": "",
        "unmatched_dir": "",
        "temp_download_dir": "temp_downloads"
    },
    "tmdb": {
        "api_key": "",
        "language": "en-US",
        "include_adult": False
    },
    "telegram": {
        "api_id": "",
        "api_hash": "",
        "bot_token": "",
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
        "chunk_size": 1048576,
        "progress_update_interval": 5,
        "max_retries": 3,
        "retry_delay": 5,
        "max_concurrent_downloads": 3,
        "verify_downloads": True,
        "temp_download_dir": "temp_downloads",
        "max_speed_mbps": None,
        "speed_limit": 0
    },
    "notification": {
        "enabled": True,
        "method": "telegram"
    }
}

def validate_path(ctx, param, value):
    """Validate and create directory if it doesn't exist."""
    path = Path(value)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())
    except Exception as e:
        raise click.BadParameter(f"Invalid path: {str(e)}")

def validate_numeric_string(ctx, param, value):
    """Validate that string contains only numbers."""
    if not value.isdigit():
        raise click.BadParameter("Must contain only numbers")
    return value

@click.command()
@click.option('--download-dir', prompt='Enter path for downloads directory',
              help='Directory where files will be downloaded',
              callback=validate_path)
@click.option('--movies-dir', prompt='Enter path for movies directory',
              help='Directory where movies will be organized',
              callback=validate_path)
@click.option('--tv-dir', prompt='Enter path for TV shows directory',
              help='Directory where TV shows will be organized',
              callback=validate_path)
@click.option('--unmatched-dir', prompt='Enter path for unmatched media directory',
              help='Directory for unmatched media files',
              callback=validate_path)
@click.option('--tmdb-key', prompt='Enter TMDB API key',
              help='API key for The Movie Database')
@click.option('--telegram-api-id', prompt='Enter Telegram API ID',
              help='Telegram API ID',
              callback=validate_numeric_string)
@click.option('--telegram-api-hash', prompt='Enter Telegram API hash',
              help='Telegram API hash')
@click.option('--telegram-bot-token', prompt='Enter Telegram bot token',
              help='Token for your Telegram bot')
@click.option('--telegram-chat-id', prompt='Enter Telegram chat ID',
              help='Chat ID for notifications',
              callback=validate_numeric_string)
def init_config(download_dir, movies_dir, tv_dir, unmatched_dir,
                tmdb_key, telegram_api_id, telegram_api_hash,
                telegram_bot_token, telegram_chat_id):
    """Initialize the Media Manager configuration."""
    try:
        # Create .env file with secrets
        env_content = f"""
TMDB_API_KEY={tmdb_key}
TELEGRAM_API_ID={telegram_api_id}
TELEGRAM_API_HASH={telegram_api_hash}
TELEGRAM_BOT_TOKEN={telegram_bot_token}
TELEGRAM_CHAT_ID={telegram_chat_id}
"""
        with open('.env', 'w') as f:
            f.write(env_content.strip())
        click.echo("Created .env file with secrets")

        # Create config.json without sensitive data
        config = CONFIG_TEMPLATE.copy()
        config["paths"]["telegram_download_dir"] = download_dir
        config["paths"]["movies_dir"] = movies_dir
        config["paths"]["tv_shows_dir"] = tv_dir
        config["paths"]["unmatched_dir"] = unmatched_dir

        # Remove sensitive data from config (will be loaded from env)
        config["tmdb"]["api_key"] = "${TMDB_API_KEY}"
        config["telegram"]["api_id"] = "${TELEGRAM_API_ID}"
        config["telegram"]["api_hash"] = "${TELEGRAM_API_HASH}"
        config["telegram"]["bot_token"] = "${TELEGRAM_BOT_TOKEN}"
        config["telegram"]["chat_id"] = "${TELEGRAM_CHAT_ID}"
        config["notification"]["bot_token"] = "${TELEGRAM_BOT_TOKEN}"
        config["notification"]["chat_id"] = "${TELEGRAM_CHAT_ID}"

        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        click.echo("Created config.json")

        click.echo("\nConfiguration completed successfully!")
        click.echo("Make sure to add .env to your .gitignore")

    except Exception as e:
        click.echo(f"Error creating configuration: {str(e)}", err=True)
        raise click.Abort()

if __name__ == '__main__':
    init_config()