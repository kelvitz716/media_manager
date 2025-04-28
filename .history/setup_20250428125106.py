"""Setup script for media manager package."""
from setuptools import setup, find_packages

setup(
    name="media_manager",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot>=20.7",
        "telethon>=1.33.1",
        "aiohttp>=3.9.1",
        "watchdog>=3.0.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "asyncio>=3.4.3"
    ],
    author="Kelvitz",
    description="A media manager that downloads from Telegram and organizes files",
    python_requires=">=3.8",
)