"""Tests for logger setup functionality."""
import os
import logging
import pytest
from media_manager.common.logger_setup import setup_logging

def test_setup_logging_default_values():
    """Test logger setup with default configuration."""
    config = {}
    logger = setup_logging(config)
    
    assert isinstance(logger, logging.Logger)
    assert logger.name == "MediaManager"
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 2
    assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers)
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)

def test_setup_logging_custom_values():
    """Test logger setup with custom configuration."""
    config = {
        "level": "DEBUG",
        "max_size_mb": 20,
        "backup_count": 3
    }
    logger = setup_logging(config, name="TestLogger")
    
    assert logger.name == "TestLogger"
    assert logger.level == logging.DEBUG
    
    file_handler = next(h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler))
    assert file_handler.maxBytes == 20 * 1024 * 1024
    assert file_handler.backupCount == 3

def test_setup_logging_file_creation():
    """Test log file creation."""
    config = {}
    logger = setup_logging(config)
    
    log_file = "media_watcher.log"
    assert os.path.exists(log_file)
    
    # Cleanup
    try:
        os.remove(log_file)
    except OSError:
        pass

def test_setup_logging_formatter():
    """Test log formatters are properly configured."""
    config = {}
    logger = setup_logging(config)
    
    file_handler = next(h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler))
    console_handler = next(h for h in logger.handlers if isinstance(h, logging.StreamHandler))
    
    assert file_handler.formatter._fmt == '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    assert console_handler.formatter._fmt == '%(levelname)s: %(message)s'

def test_setup_logging_invalid_level():
    """Test logger setup with invalid log level."""
    config = {"level": "INVALID_LEVEL"}
    
    # Should default to INFO when invalid level is provided
    logger = setup_logging(config)
    assert logger.level == logging.INFO

def test_setup_logging_duplicate_handlers():
    """Test that handlers are not duplicated when setup_logging is called multiple times."""
    config = {}
    logger1 = setup_logging(config)
    initial_handler_count = len(logger1.handlers)
    
    # Call setup_logging again with the same name
    logger2 = setup_logging(config)
    assert len(logger2.handlers) == initial_handler_count