"""Logging setup module."""
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

MODULES = [
    "MediaManager",
    "TelegramDownloader",
    "MediaWatcher",
    "MediaFileHandler",
    "MediaCategorizer",
    "NotificationService",
    "TMDBClient"
]

def setup_logging(config):
    """Set up logging configuration."""
    # Configure root logger first
    root_logger = logging.getLogger()
    root_logger.handlers = []  # Clear existing handlers
    
    # Get logging configuration
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "DEBUG")  # Default to DEBUG
    max_size = log_config.get("max_size_mb", 10) * 1024 * 1024
    backup_count = log_config.get("backup_count", 5)
    
    # Set log level
    try:
        level = getattr(logging, log_level.upper())
    except (AttributeError, TypeError):
        level = logging.DEBUG
        
    # Set root logger level
    root_logger.setLevel(level)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(detailed_formatter)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # Setup file handler if configured
    log_dir = log_config.get("log_dir", "logs")
    log_file = log_config.get("log_file", "media_watcher.log")
    
    if log_dir and log_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_path / log_file,
            maxBytes=max_size,
            backupCount=backup_count
        )
        file_handler.setFormatter(detailed_formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    
    # Configure module loggers
    loggers = {}
    for module in MODULES:
        logger = logging.getLogger(module)
        logger.setLevel(level)
        logger.propagate = True  # Allow propagation to root logger
        loggers[module] = logger
    
    return loggers.get("MediaManager")