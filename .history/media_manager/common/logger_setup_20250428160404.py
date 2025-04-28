"""Logging configuration module."""
import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any

def setup_logging(config: Dict[str, Any], name: str = "MediaManager") -> logging.Logger:
    """
    Set up logging with rotating file handler.
    
    Args:
        config: Logging configuration dictionary
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    # Handle invalid log level by defaulting to INFO
    try:
        log_level = getattr(logging, config.get("level", "INFO").upper())
    except AttributeError:
        log_level = logging.INFO

    max_size_mb = config.get("max_size_mb", 10)
    backup_count = config.get("backup_count", 5)
    
    # Create log directory if needed
    log_dir = os.path.dirname(os.path.abspath("media_watcher.log"))
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure logging
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add rotating file handler with detailed formatter
    file_handler = RotatingFileHandler(
        "media_watcher.log",
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(file_handler)
    
    # Add console handler with simpler formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s')
    )
    logger.addHandler(console_handler)
    
    return logger