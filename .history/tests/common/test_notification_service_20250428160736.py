"""Tests for notification service."""
import pytest
import asyncio
from unittest import mock
from media_manager.common.notification_service import NotificationService

@pytest.fixture
def mock_telegram_bot():
    """Create mock telegram bot."""
    bot = mock.AsyncMock()
    bot.send_message = mock.AsyncMock()
    return bot

@pytest.fixture
def notification_service(mock_telegram_bot):
    """Create NotificationService with mock bot."""
    config = {
        "notification": {
            "enabled": True,
            "method": "telegram",
            "bot_token": "test_token",
            "chat_id": "123456789"
        }
    }
    service = NotificationService(config)
    service.bot = mock_telegram_bot
    service.configured = True  # Mark as configured since we're using a mock
    return service

@pytest.mark.asyncio
async def test_notify(notification_service):
    """Test basic notification."""
    await notification_service.notify("Test message")
    notification_service.bot.send_message.assert_called_once_with(
        chat_id="123456789",
        text="Test message"
    )

@pytest.mark.asyncio
async def test_notify_with_reply(notification_service):
    """Test notification with reply button."""
    # Mock message response
    message = mock.AsyncMock()
    message.text = "user response"
    notification_service.bot.send_message.return_value = message

    response = await notification_service.notify(
        "Test message",
        reply_markup={"inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]}
    )

    args = notification_service.bot.send_message.call_args[1]
    assert "reply_markup" in args
    assert response == message

@pytest.mark.asyncio
async def test_wait_for_response(notification_service):
    """Test waiting for user response."""
    # Mock the user's response
    future = asyncio.Future()
    future.set_result("user response")
    notification_service._get_response = mock.AsyncMock(return_value=future)

    # Wait for response
    response = await notification_service.wait_for_response(timeout=1)
    assert response == "user response"
    notification_service._get_response.assert_called_once()

@pytest.mark.asyncio
async def test_wait_for_response_timeout(notification_service):
    """Test response waiting timeout."""
    # Mock a timeout
    future = asyncio.Future()
    notification_service._get_response = mock.AsyncMock(return_value=future)

    # Wait for response with short timeout
    response = await notification_service.wait_for_response(timeout=0.1)
    assert response is None

def test_register_command(notification_service):
    """Test command registration."""
    async def handler(update, context):
        pass

    notification_service.register_command("test", handler)
    assert "test" in notification_service.command_handlers

@pytest.mark.asyncio
async def test_handle_response(notification_service):
    """Test handling command response."""
    # Register a test command
    received_args = []
    async def handler(update, context):
        received_args.extend([update, context])
        return "handled"

    notification_service.register_command("test", handler)

    # Mock update and context
    update = mock.AsyncMock()
    context = mock.AsyncMock()
    result = await notification_service.handle_response(
        command="test",
        update=update,
        context=context
    )

    assert result == "handled"
    assert received_args == [update, context]

@pytest.mark.asyncio
async def test_service_lifecycle(notification_service):
    """Test service start and stop."""
    # Start service
    await notification_service.start()
    notification_service.bot.start.assert_called_once()

    # Stop service
    await notification_service.stop()
    notification_service.bot.stop.assert_called_once()

def test_notify_without_telegram(notification_service):
    """Test notification when telegram is not configured."""
    notification_service.configured = False
    notification_service.notify("Test message")  # Should not raise exception

def test_error_handling(notification_service):
    """Test error handling in notification service."""
    notification_service.bot.send_message.side_effect = Exception("Test error")
    notification_service.notify("Test message")  # Should not raise exception