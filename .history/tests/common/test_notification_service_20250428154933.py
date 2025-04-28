"""Tests for the notification service component."""
import pytest
import asyncio
from unittest import mock
from typing import Dict, Any
from telebot.async_telebot import AsyncTeleBot
from media_manager.common.notification_service import NotificationService

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "enabled": True,
        "method": "telegram",
        "telegram": {
            "bot_token": "test_token",
            "chat_id": "123456789"
        }
    }

@pytest.fixture
def notification_service(mock_config):
    """Create NotificationService instance."""
    return NotificationService(mock_config)

@pytest.mark.asyncio
async def test_notify(notification_service):
    """Test sending notifications."""
    # Test telegram notification
    notification_service.bot = mock.AsyncMock(spec=AsyncTeleBot)
    
    await notification_service.notify("Test message", "info")
    
    notification_service.bot.send_message.assert_called_once()
    args = notification_service.bot.send_message.call_args[1]
    assert args["chat_id"] == "123456789"
    assert "Test message" in args["text"]
    assert args["parse_mode"] == "HTML"

@pytest.mark.asyncio
async def test_notify_with_reply(notification_service):
    """Test notifications with reply."""
    notification_service.bot = mock.AsyncMock(spec=AsyncTeleBot)
    
    await notification_service.notify("Test reply", "info", reply_to=123)
    
    args = notification_service.bot.send_message.call_args[1]
    assert args["reply_to_message_id"] == 123

@pytest.mark.asyncio
async def test_wait_for_response(notification_service):
    """Test waiting for user response."""
    notification_service.bot = mock.AsyncMock(spec=AsyncTeleBot)
    
    # Mock successful response
    response_future = asyncio.Future()
    response_future.set_result("user response")
    notification_service._waiting_for_response = {123: response_future}
    
    # Send prompt and wait for response
    notification_service.bot.send_message = mock.AsyncMock(
        return_value=mock.Mock(message_id=123)
    )
    
    response = await notification_service.wait_for_response("Test prompt")
    assert response == "user response"

@pytest.mark.asyncio
async def test_wait_for_response_timeout(notification_service):
    """Test response timeout."""
    notification_service.bot = mock.AsyncMock(spec=AsyncTeleBot)
    
    # Mock message send
    notification_service.bot.send_message = mock.AsyncMock(
        return_value=mock.Mock(message_id=123)
    )
    
    # Test with short timeout
    response = await notification_service.wait_for_response("Test prompt", timeout=0.1)
    assert response is None

@pytest.mark.asyncio
async def test_register_command(notification_service):
    """Test command registration."""
    notification_service.bot = mock.AsyncMock(spec=AsyncTeleBot)
    
    callback = mock.AsyncMock()
    await notification_service.register_command("test", callback)
    
    # Get registered handler
    handler = notification_service.bot.message_handler.call_args[1]["commands"][0]
    assert handler == "test"

@pytest.mark.asyncio
async def test_handle_response(notification_service):
    """Test handling incoming responses."""
    # Create waiting future
    future = asyncio.Future()
    notification_service._waiting_for_response[123] = future
    
    # Handle response
    notification_service.handle_response(123, "test response")
    
    assert future.done()
    assert future.result() == "test response"

@pytest.mark.asyncio
async def test_service_lifecycle(notification_service):
    """Test service start/stop."""
    notification_service.bot = mock.AsyncMock(spec=AsyncTeleBot)
    
    # Test start
    await notification_service.start()
    notification_service.bot.delete_webhook.assert_called_once_with(drop_pending_updates=True)
    
    # Test stop
    await notification_service.stop()
    notification_service.bot.close_session.assert_called_once()

@pytest.mark.asyncio
async def test_notify_without_telegram(mock_config):
    """Test notifications without Telegram configured."""
    mock_config["method"] = "print"
    service = NotificationService(mock_config)
    
    # Should not raise error
    await service.notify("Test message")

@pytest.mark.asyncio
async def test_error_handling(notification_service):
    """Test error handling in notifications."""
    notification_service.bot = mock.AsyncMock(spec=AsyncTeleBot)
    notification_service.bot.send_message.side_effect = Exception("Test error")
    
    # Should not raise error
    await notification_service.notify("Test message")