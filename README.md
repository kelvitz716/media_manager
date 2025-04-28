# Media Manager

A Python-based media manager that integrates with Telegram to download and organize media files. It automatically categorizes movies and TV shows using TMDB metadata.

## Features

- Telegram bot integration for downloading media files
- Automatic media categorization based on filenames
- TMDB integration for metadata lookup
- Manual categorization support via Telegram commands
- Progress notifications and status updates
- Configurable download paths and settings
- Rate limiting and download speed control

## Requirements

- Python 3.8 or higher
- Telegram Bot API credentials
- TMDB API key

## Installation

1. Clone the repository
2. Create a virtual environment
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/Mac
   # or
   .venv\Scripts\activate  # On Windows
   ```
3. Install the package:
   ```bash
   pip install -e .
   ```

## Configuration

Configuration can be done through either `config.json` or environment variables. Environment variables take precedence over config file values.

### Using config.json

1. Copy `config.json` and fill in your credentials:
   - Telegram API credentials (`api_id`, `api_hash`, `bot_token`)
   - TMDB API key
   - Chat ID for notifications
   - Customize paths and other settings as needed

### Using Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials and settings:
   ```bash
   # Required
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   TMDB_API_KEY=your_tmdb_api_key

   # Optional
   LOG_LEVEL=INFO
   MAX_CONCURRENT_DOWNLOADS=3
   MAX_SPEED_MBPS=0  # 0 for unlimited
   ```

## Development Setup

1. Create a development environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/Mac
   # or
   .venv\Scripts\activate  # On Windows
   ```

2. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Testing

Run the test suite:
```bash
pytest
```

Run with coverage report:
```bash
pytest --cov=media_manager

# For HTML coverage report
pytest --cov=media_manager --cov-report=html
```

## Code Quality

The project uses several tools to maintain code quality:

- **Black** for code formatting
  ```bash
  black media_manager/
  ```

- **isort** for import sorting
  ```bash
  isort media_manager/
  ```

- **mypy** for type checking
  ```bash
  mypy media_manager/
  ```

- **pylint** for code analysis
  ```bash
  pylint media_manager/
  ```

## Project Structure

```
media_manager/
├── main.py                 # Main entry point
├── config.json             # Configuration file
├── common/                 # Shared components
│   ├── config_manager.py
│   ├── logger_setup.py
│   ├── notification_service.py
│   └── rate_limiters.py
├── downloader/            # Telegram downloader
│   ├── bot.py
│   └── run_downloader.py
├── watcher/              # File processor
│   ├── categorizer.py
│   ├── file_mover.py
│   ├── tmdb_client.py
│   └── run_watcher.py
└── tests/               # Unit tests
    ├── common/
    ├── downloader/
    └── watcher/

## License

MIT License