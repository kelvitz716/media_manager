"""Test configuration and fixtures."""
import os
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure asyncio for testing
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "asyncio_mode",
        "strict"
    )