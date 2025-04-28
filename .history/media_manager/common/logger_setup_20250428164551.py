"""Logging setup module."""
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(config):
    """Set up logging configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger()
    
    # Clear existing handlers to avoid duplicates
    logger.handlers = []
    
    # Get logging configuration
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO")
    max_size = log_config.get("max_size_mb", 10) * 1024 * 1024
    backup_count = log_config.get("backup_count", 5)
    
    # Set log level
    try:
        logger.setLevel(getattr(logging, log_level.upper()))
    except (AttributeError, TypeError):
        logger.setLevel(logging.INFO)
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
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
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger