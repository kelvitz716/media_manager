# Media Manager

A Telegram bot that downloads and automatically organizes media files into a Jellyfin/Plex-compatible directory structure.

## Features

- Downloads media files from Telegram
- Automatically categorizes movies and TV shows
- Organizes files into proper directory structure
- Integrates with TMDB for metadata
- Supports Docker deployment
- Secure secrets management

## Setup

### Prerequisites

- Python 3.12 or higher
- Docker and Docker Compose (for containerized deployment)
- A Telegram Bot Token (from @BotFather)
- Telegram API credentials (from https://my.telegram.org/apps)
- TMDB API key (from https://www.themoviedb.org/settings/api)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd media-manager
   ```

2. Run the initialization script to set up your configuration:
   ```bash
   python scripts/init_config.py
   ```
   The script will prompt you for:
   - Download directory path (where files will be downloaded)
   - Movies directory path (where movies will be organized)
   - TV Shows directory path (where TV shows will be organized)
   - Unmatched directory path (for files that couldn't be categorized)
   - TMDB API key
   - Telegram API credentials
   - Telegram bot token
   - Telegram chat ID

3. Generate Docker secrets:
   ```bash
   ./scripts/setup_secrets.sh
   ```

### Running with Docker (Recommended)

1. Start the container:
   ```bash
   docker compose up -d
   ```

The container will automatically handle secrets and mount your media directories.

### Environment Variables

You can customize the media paths by setting these environment variables:
- `DOWNLOAD_PATH`: Override the default downloads directory
- `MEDIA_PATH`: Override the default media directory root

Example:
```bash
DOWNLOAD_PATH=/my/downloads MEDIA_PATH=/my/media docker compose up -d
```

### Development Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python -m media_manager.main
   ```

## Usage

1. Start a chat with your bot on Telegram
2. Send media files or use supported commands:
   - `/start` - Get started with the bot
   - `/help` - Show available commands
   - `/categorize` - Manually categorize a file
   - `/status` - Check bot status

## Configuration

The configuration is split between:
- `config.json`: Contains non-sensitive settings
- Docker secrets/Environment variables: Contains sensitive data
  - TMDB_API_KEY
  - TELEGRAM_API_ID
  - TELEGRAM_API_HASH
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

[Your License Here]