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
    log_level = getattr(logging, config.get("level", "INFO"))
    max_size_mb = config.get("max_size_mb", 10)
    backup_count = config.get("backup_count", 5)
    
    # Create log directory if needed
    log_dir = os.path.dirname(os.path.abspath("media_watcher.log"))
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure logging
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Add rotating file handler
    file_handler = RotatingFileHandler(
        "media_watcher.log",
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s')
    )
    
    # Add handlers if they don't exist
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger