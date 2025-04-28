"""Tests for notification service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from media_manager.common.notification_service import NotificationService

@pytest.mark.asyncio
async def test_notify(notification_service):
    """Test basic notification."""
    notification_service.bot.send_message = AsyncMock()
    await notification_service.notify("test message")
    notification_service.bot.send_message.assert_called_once_with(
        chat_id=notification_service.config["notification"]["chat_id"],
        text="test message"
    )

@pytest.mark.asyncio
async def test_notify_with_reply(notification_service):
    """Test notification with reply."""
    notification_service.bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))
    
    # Simulate response by directly calling handle_update
    async def send_message(*args, **kwargs):
        msg = MagicMock(message_id=123)
        
        # Simulate response
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_to_message = MagicMock(message_id=123)
        update.message.text = "user response"
        await notification_service.handle_update(update)
        
        return msg

    notification_service.bot.send_message = AsyncMock(side_effect=send_message)
    response = await notification_service.notify("test message", wait_response=True)
    assert response == "user response"

@pytest.mark.asyncio
async def test_response_timeout(notification_service):
    """Test notification response timeout."""
    notification_service.bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))
    response = await notification_service.notify("test message", wait_response=True, response_timeout=0.1)
    assert response is None

@pytest.mark.asyncio
async def test_multiple_responses(notification_service):
    """Test handling multiple responses."""
    message_ids = [123, 456]
    messages = ["message 1", "message 2"]
    responses = ["response 1", "response 2"]
    current_idx = 0

    async def send_message(*args, **kwargs):
        nonlocal current_idx
        msg = MagicMock(message_id=message_ids[current_idx])
        
        # Simulate response
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_to_message = MagicMock(message_id=message_ids[current_idx])
        update.message.text = responses[current_idx]
        await notification_service.handle_update(update)
        
        current_idx += 1
        return msg

    notification_service.bot.send_message = AsyncMock(side_effect=send_message)
    received_responses = await notification_service.notify_all(messages, wait_responses=True)
    assert received_responses == responses

@pytest.mark.asyncio
async def test_command_handling(notification_service):
    """Test command registration and handling."""
    command_handler = AsyncMock()
    await notification_service.register_command("test", command_handler)
    await notification_service._handle_command("test", "args")
    command_handler.assert_called_once_with("args")