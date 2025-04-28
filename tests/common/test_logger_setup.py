"""Tests for logger setup module."""
import os
import logging
import pytest
from pathlib import Path
from media_manager.common.logger_setup import setup_logging

@pytest.fixture
def config():
    """Test configuration."""
    return {
        "logging": {
            "level": "DEBUG",
            "max_size_mb": 10,
            "backup_count": 5,
            "log_dir": "logs",
            "log_file": "test.log"
        }
    }

def test_setup_logging_default_values():
    """Test setup_logging with default values."""
    logger = setup_logging({})
    assert logger.level == logging.INFO
    
    # Check handlers
    has_stream_handler = any(isinstance(h, logging.StreamHandler) 
                           for h in logger.handlers)
    assert has_stream_handler

def test_setup_logging_custom_values(config):
    """Test setup_logging with custom values."""
    logger = setup_logging(config)
    assert logger.level == logging.DEBUG
    
    # Check handlers
    file_handler = next((h for h in logger.handlers 
                        if isinstance(h, logging.handlers.RotatingFileHandler)), None)
    assert file_handler is not None
    assert file_handler.maxBytes == config["logging"]["max_size_mb"] * 1024 * 1024
    assert file_handler.backupCount == config["logging"]["backup_count"]

def test_setup_logging_file_creation(config, tmp_path):
    """Test log file creation."""
    # Use temporary directory for log file
    config["logging"]["log_dir"] = str(tmp_path)
    logger = setup_logging(config)
    
    log_file = Path(tmp_path) / config["logging"]["log_file"]
    assert log_file.exists()
    
    # Test logging
    test_message = "Test log message"
    logger.info(test_message)
    
    with open(log_file, 'r') as f:
        log_content = f.read()
        assert test_message in log_content

def test_setup_logging_formatter():
    """Test logging formatter configuration."""
    logger = setup_logging({})
    console_handler = next(h for h in logger.handlers 
                         if isinstance(h, logging.StreamHandler))
    assert console_handler.formatter._fmt == '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def test_setup_logging_invalid_level():
    """Test handling invalid log level."""
    logger = setup_logging({"logging": {"level": "INVALID"}})
    assert logger.level == logging.INFO  # Should fall back to default

def test_setup_logging_duplicate_handlers():
    """Test no duplicate handlers are added."""
    logger = setup_logging({})
    initial_handlers = len(logger.handlers)
    
    # Setup again
    logger = setup_logging({})
    assert len(logger.handlers) == initial_handlers  # Should not add duplicate handlers