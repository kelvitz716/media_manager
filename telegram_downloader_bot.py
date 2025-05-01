#!/usr/bin/env python3
"""
telegram_downloader.py - Downloads media files from Telegram

A modular, asynchronous Telegram downloader for media files with support for
batch downloads, progress tracking, and queuing.
"""
import os
from pathlib import Path
import shutil
import time
import json
import logging
import asyncio
import random
import hashlib
import aiohttp
import telebot
import requests
from typing import Dict, List, Optional, Union, Any, Set, Deque
from dataclasses import asdict, dataclass, field
from logging.handlers import RotatingFileHandler
from collections import deque
from telebot.async_telebot import AsyncTeleBot
from telethon import TelegramClient
from telethon.errors import FloodWaitError, AuthKeyError, SessionPasswordNeededError
from media_manager.watcher.categorizer import MediaCategorizer

# Configuration constants
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "telegram": {
        "api_id": "api_id",
        "api_hash": "api_hash",
        "bot_token": "bot_token",
        "enabled": True
    },
    "paths": {
        "telegram_download_dir": "telegram_download_dir",
        "movies_dir": "/path/to/movies",
        "tv_shows_dir": "/path/to/tv_shows",
        "unmatched_dir": "/path/to/unmatched"
    },
    "logging": {
        "level": "INFO",
        "max_size_mb": 10,
        "backup_count": 5
    },
    "download": {
        "chunk_size": 1024 * 1024,  # 1MB
        "progress_update_interval": 5,  # seconds
        "max_retries": 3,
        "retry_delay": 5,  # seconds
        "max_concurrent_downloads": 3,  # concurrent downloads
        "verify_downloads": True,
        "max_speed_mbps": 0,  # 0 = unlimited
        "resume_support": True,
        "temp_download_dir": "temp_downloads"
    }
}

# Global logger
logger = None

@dataclass
class DownloadTask:
    """Represents a single download task."""
    file_id: str
    file_path: str
    file_size: int
    chat_id: int
    message_id: int
    original_message: object = None
    file_name: str = ""
    batch_id: str = None  # For grouping files in the same batch
    position: int = 0  # Position in batch
    total_files: int = 1  # Total files in batch
    resume_position: int = 0
    temp_path: str = ""
    
    # Status tracking
    status: str = "queued"  # queued, downloading, completed, failed
    
    # Add timestamp for sorting/prioritization
    added_time: float = field(default_factory=time.time)
    
    # Progress tracking
    downloaded_bytes: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    retries: int = 0

    async def prepare_resume(self) -> None:
        """Prepare for resume by checking existing partial download."""
        if os.path.exists(self.temp_path):
            self.resume_position = os.path.getsize(self.temp_path)
            self.downloaded_bytes = self.resume_position

@dataclass
class DownloadStats:
    """Statistics for download operations."""
    total_downloads: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    total_bytes: int = 0
    start_time: float = 0.0
    peak_concurrent: int = 0
    last_saved: float = 0.0

class SpeedLimiter:
    def __init__(self, max_speed_mbps: float = None):
        self.max_speed_mbps = max_speed_mbps
        self._last_check = time.time()
        self._bytes_since_check = 0
        self._lock = asyncio.Lock()

    async def limit(self, chunk_size: int) -> None:
        if not self.max_speed_mbps:
            return

        async with self._lock:
            self._bytes_since_check += chunk_size
            current_time = time.time()
            elapsed = current_time - self._last_check
            
            if elapsed >= 1:  # Check every second
                current_speed_mbps = (self._bytes_since_check * 8) / (1024 * 1024 * elapsed)
                if current_speed_mbps > self.max_speed_mbps:
                    sleep_time = (current_speed_mbps / self.max_speed_mbps - 1) * elapsed
                    await asyncio.sleep(sleep_time)
                
                self._bytes_since_check = 0
                self._last_check = time.time()

class StatsManager:
    """Manages persistent download statistics."""
    
    def __init__(self, stats_file: str = "download_stats.json"):
        self.stats_file = Path(stats_file)
        self.stats = self._load_stats()
        self._save_lock = asyncio.Lock()
        
    def _load_stats(self) -> DownloadStats:
        """Load statistics from file or create new."""
        try:
            if self.stats_file.exists():
                with open(self.stats_file) as f:
                    data = json.load(f)
                    return DownloadStats(**data)
        except Exception as e:
            logger.error(f"Failed to load stats: {e}")
        return DownloadStats(start_time=time.time())
    
    async def save_stats(self) -> None:
        """Save current statistics to file asynchronously."""
        async with self._save_lock:
            try:
                self.stats.last_saved = time.time()
                stats_data = asdict(self.stats)
                await asyncio.to_thread(self._write_stats_to_file, stats_data)
            except Exception as e:
                logger.error(f"Failed to save stats: {e}")

    def _write_stats_to_file(self, stats_data: dict) -> None:
        """Helper method to write stats to file."""
        with open(self.stats_file, 'w') as f:
            json.dump(stats_data, f, indent=4)

    async def update(self, **kwargs) -> None:
        """Update statistics with new values."""
        for key, value in kwargs.items():
            if hasattr(self.stats, key):
                setattr(self.stats, key, value)
        
        # Auto-save every 5 minutes
        if time.time() - self.stats.last_saved > 300:
            await self.save_stats()

class RateLimiter:
    """Manages rate limiting for API calls and notifications."""
    
    def __init__(self, min_interval: float = 2.0):
        """
        Initialize rate limiter.
        
        Args:
            min_interval: Minimum seconds between updates for each chat
        """
        self.last_update: Dict[Union[int, str], float] = {}
        self.min_interval = min_interval
        self.lock = asyncio.Lock()
        
    async def can_update(self, chat_id: Union[int, str]) -> bool:
        """
        Check if an update is allowed for the given chat ID.
        
        Args:
            chat_id: The chat ID or unique identifier
            
        Returns:
            True if an update is allowed, False otherwise
        """
        async with self.lock:
            now = time.time()
            if chat_id not in self.last_update:
                self.last_update[chat_id] = now
                return True
            
            # Check if enough time has passed
            if now - self.last_update[chat_id] >= self.min_interval:
                self.last_update[chat_id] = now
                return True
            return False
            
    async def wait_if_needed(self, chat_id: Union[int, str]) -> None:
        """
        Wait until an update is allowed for the given chat ID.
        
        Args:
            chat_id: The chat ID or unique identifier
        """
        async with self.lock:
            now = time.time()
            if chat_id in self.last_update:
                time_since_last = now - self.last_update[chat_id]
                if time_since_last < self.min_interval:
                    wait_time = self.min_interval - time_since_last
                    await asyncio.sleep(wait_time)
            
            self.last_update[chat_id] = time.time()


class TelegramBot:
    """Handles Telegram bot interactions and commands."""

    def __init__(self, config_manager, download_manager):
        """Initialize the bot."""
        self.config = config_manager
        self.download_manager = download_manager
        self.bot = None
        self.running = False
        self.polling_task = None
        self.connection_check_task = None

    async def start(self) -> None:
        """Start the Telegram bot."""
        if not self.config.get("telegram", "enabled", default=False):
            logger.info("Telegram bot is disabled in config")
            return

        try:
            logger.info("Starting Telegram bot...")
            # Initialize bot
            bot_token = self.config.get("telegram", "bot_token")
            if not bot_token:
                raise ValueError("Bot token not configured")

            self.bot = AsyncTeleBot(bot_token)
            self._setup_handlers()
            
            # Start polling task
            self.running = True
            self.polling_task = asyncio.create_task(self._polling_task())
            self.connection_check_task = asyncio.create_task(self._connection_check())
            
            logger.info("Telegram bot started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {str(e)}")
            self.running = False
            raise

    def _setup_handlers(self) -> None:
        """Set up Telegram bot message handlers."""

        @self.bot.message_handler(commands=['start', 'help'])
        async def send_welcome(message):
            """Handle /start and /help commands."""
            welcome_text = (
                "👋 Welcome to the Media Manager Bot!\n\n"
                "I can help you manage your media files. Send me any media file "
                "and I'll automatically categorize and organize it.\n\n"
                "📂 Available Commands:\n"
                "/start - Show this welcome message\n"
                "/status - 📊 Show active downloads\n"
                "/queue - 📋 View download queue\n"
                "/test - 🔍 Run system test\n"
                "/help - ❓ Show this help message\n\n"
                "📱 Supported Formats:\n"
                "🎬 Videos - MP4, MKV, AVI, etc.\n"
                "🎵 Audio - MP3, FLAC, WAV, etc.\n"
                "📄 Documents - PDF, ZIP, etc.\n\n"
                "Just send me any supported file to begin!"
            )
            try:
                await self.bot.reply_to(message, welcome_text)
            except Exception as e:
                logger.error(f"Error sending welcome message: {e}")

        @self.bot.message_handler(commands=['status'])
        async def show_status(message):
            """Handle /status command."""
            try:
                active_downloads = self.download_manager.get_active_downloads()
                if not active_downloads:
                    await self.bot.reply_to(message, "📥 No active downloads")
                    return

                status_text = "📥 Active Downloads:\n\n"
                for download in active_downloads:
                    status_text += f"- {download.filename}: {download.progress:.1f}%\n"
                await self.bot.reply_to(message, status_text)
            except Exception as e:
                logger.error(f"Error showing status: {e}")
                await self.bot.reply_to(message, "❌ Failed to get download status")

        @self.bot.message_handler(commands=['queue'])
        async def show_queue(message):
            """Handle /queue command."""
            try:
                queue_status = self.download_manager.get_queue_status()
                await self.bot.reply_to(message, queue_status)
            except Exception as e:
                logger.error(f"Error showing queue: {e}")
                await self.bot.reply_to(message, "❌ Failed to get queue status")

        @self.bot.message_handler(commands=['test'])
        async def run_test(message):
            """Handle /test command."""
            test_results = ["🔍 Running system tests..."]
            
            # Test Telegram API
            try:
                me = await self.bot.get_me()
                test_results.append(f"✅ Telegram Bot API is working ({me.username})")
            except Exception as e:
                test_results.append(f"❌ Telegram Bot API test failed: {str(e)}")

            # Test internet connection
            connection_speed = "Unknown"
            try:
                start_time = time.time()
                session = aiohttp.ClientSession()
                async with session.get("https://www.google.com", timeout=5) as response:
                    resp = await response.read()
                    download_time = time.time() - start_time
                    connection_speed = f"{len(resp) / download_time / 1024:.1f} KB/s"
                    if response.status == 200:
                        test_results.append(f"✅ Internet connection is working")
                    else:
                        test_results.append(f"❌ Internet connection test failed: HTTP {response.status}")
                await session.close()
            except Exception as e:
                test_results.append(f"❌ Internet connection test failed: {str(e)}")

            # Test disk space
            try:
                download_dir = self.download_manager.download_dir
                if os.path.exists(download_dir):
                    total, used, free = shutil.disk_usage(download_dir)
                    free_gb = free / (1024**3)
                    test_results.append(f"✅ Available disk space: {free_gb:.1f} GB")
                    if free_gb < 1:
                        test_results.append(f"⚠️ Warning: Less than 1GB free space")
            except Exception as e:
                test_results.append(f"❌ Failed to check disk space: {str(e)}")
            
            # Test queue system
            test_results.append(f"✅ Download queue system is active (limit: {self.download_manager.max_concurrent_downloads})")

            # Performance metrics
            perf_results = [
                f"\nPERFORMANCE METRICS:",
                f"⚡ Network speed: {connection_speed}",
                f"⏱️ API response time: {download_time*1000:.0f}ms" + (" (Normal)" if download_time < 1 else " (Slow)")
            ]
            
            # Send results
            try:
                await self.bot.reply_to(
                    message,
                    "\n".join(test_results + perf_results)
                )
            except Exception as e:
                logger.error(f"Failed to send test results: {e}")

        @self.bot.message_handler(content_types=['document', 'video', 'audio'])
        async def handle_media(message):
            """Handle media file downloads."""
            try:
                await self.download_manager.process_media_message(message)
            except Exception as e:
                error_msg = f"Failed to process media: {str(e)}"
                logger.error(error_msg)
                await self.bot.reply_to(message, f"❌ {error_msg}")

    async def _polling_task(self) -> None:
        """Background task for polling updates."""
        while self.running:
            try:
                await self.bot.polling(non_stop=True, timeout=60)
            except Exception as e:
                logger.error(f"Polling error: {str(e)}")
                await asyncio.sleep(5)

    async def _connection_check(self) -> None:
        """Periodic connection check task."""
        while self.running:
            try:
                await self.bot.get_me()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Connection check failed: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self.running = False
        if self.polling_task:
            self.polling_task.cancel()
        if self.connection_check_task:
            self.connection_check_task.cancel()
        
        if self.bot:
            try:
                # Close bot session
                await self.bot.close_session()
            except Exception as e:
                logger.error(f"Error closing bot session: {e}")
            self.bot = None