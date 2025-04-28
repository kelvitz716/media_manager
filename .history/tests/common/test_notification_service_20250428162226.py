"""Tests for the notification service."""
import pytest
import asyncio
import time
from unittest import mock
from media_manager.common.config_manager import ConfigManager
from media_manager.common.notification_service import NotificationService

@pytest.fixture
def telegram_config():
    """Telegram configuration for testing."""
    return {
        "telegram": {
            "bot_token": "test_token",
            "chat_id": "123456789"
        },
        "notification": {
            "enabled": True,
            "method": "telegram",
            "bot_token": "test_token",
            "chat_id": "123456789"
        }
    }

@pytest.fixture
async def notification_service(telegram_config):
    """Create notification service instance with mocked telegram bot."""
    config_manager = mock.Mock(spec=ConfigManager)
    config_manager.config = telegram_config
    config_manager.__getitem__ = lambda self, key: self.config.get(key, {})
    
    # Create service with mocked bot
    service = NotificationService(config_manager)
    
    # Mock telegram bot methods
    service.bot = mock.AsyncMock()
    service.bot.send_message = mock.AsyncMock()
    service._initialize_bot = mock.AsyncMock()
    
    await service.start()
    yield service
    await service.stop()

@pytest.mark.asyncio
async def test_notify(notification_service):
    """Test sending notification."""
    await notification_service.notify("Test message")
    notification_service.bot.send_message.assert_called_once_with(
        chat_id="123456789",
        text="Test message"
    )

@pytest.mark.asyncio
async def test_notify_with_reply(notification_service):
    """Test notification with reply handling."""
    response_text = "user response"
    notification_service.bot.send_message.return_value = mock.AsyncMock(
        id=123,
        text=response_text
    )
    
    # Simulate user reply
    async def simulate_reply():
        await asyncio.sleep(0.1)
        notification_service._handle_response(123, response_text)
    
    # Send notification and wait for reply
    asyncio.create_task(simulate_reply())
    response = await notification_service.notify("Test message", wait_response=True)
    
    assert response == response_text
    notification_service.bot.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_wait_for_response(notification_service):
    """Test waiting for response."""
    response_text = "user response"
    msg_id = 123
    
    # Simulate delayed response
    async def simulate_response():
        await asyncio.sleep(0.1)
        notification_service._handle_response(msg_id, response_text)
    
    # Start waiting and simulate response
    asyncio.create_task(simulate_response())
    response = await notification_service.wait_for_response(msg_id)
    
    assert response == response_text

@pytest.mark.asyncio
async def test_wait_for_response_timeout(notification_service):
    """Test response timeout."""
    msg_id = 123
    response = await notification_service.wait_for_response(msg_id, timeout=0.1)
    assert response is None

@pytest.mark.asyncio
async def test_register_command(notification_service):
    """Test command registration."""
    cmd_name = "test"
    cmd_handler = mock.AsyncMock()
    
    notification_service.register_command(cmd_name, cmd_handler)
    await notification_service._handle_command(cmd_name, "arg1 arg2")
    
    cmd_handler.assert_called_once_with("arg1 arg2")

@pytest.mark.asyncio
async def test_handle_response(notification_service):
    """Test response handling."""
    msg_id = 123
    response_text = "test response"
    
    notification_service._handle_response(msg_id, response_text)
    assert notification_service._waiting_responses[msg_id].result() == response_text

@pytest.mark.asyncio
async def test_service_lifecycle(notification_service):
    """Test service start/stop."""
    assert notification_service.running
    await notification_service.stop()
    assert not notification_service.running
    await notification_service.start()
    assert notification_service.running

@pytest.mark.asyncio
async def test_notify_without_telegram(telegram_config):
    """Test notification when telegram is not configured."""
    config_manager = mock.Mock(spec=ConfigManager)
    config_manager.config = {
        "notification": {
            "enabled": True,
            "method": "print"
        }
    }
    config_manager.__getitem__ = lambda self, key: self.config.get(key, {})
    
    service = NotificationService(config_manager)
    await service.start()
    
    # Should not raise error
    await service.notify("Test message")
    await service.stop()

@pytest.mark.asyncio
async def test_error_handling(notification_service):
    """Test error handling during notification."""
    notification_service.bot.send_message.side_effect = Exception("Test error")
    
    # Should not raise error
    await notification_service.notify("Test message")
    notification_service.bot.send_message.assert_called_once()