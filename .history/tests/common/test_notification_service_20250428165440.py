"""Tests for notification service module."""
import pytest
import asyncio
from unittest import mock

from media_manager.common.notification_service import NotificationService

@pytest.mark.asyncio
async def test_notify(notification_service):
    """Test basic notification."""
    message = "Test message"
    await notification_service.notify(message)
    notification_service.bot.send_message.assert_called_once_with(
        chat_id=notification_service.chat_id,
        text=message
    )

@pytest.mark.asyncio
async def test_notify_with_reply(notification_service):
    """Test notification with reply handling."""
    response_text = "user response"
    msg_id = 123
    
    # Set up mock response
    mock_msg = mock.AsyncMock()
    mock_msg.message_id = msg_id
    notification_service.bot.send_message.return_value = mock_msg

    # Create future for response
    notification_service._waiting_responses[msg_id] = asyncio.Future()
    notification_service._waiting_responses[msg_id].set_result(response_text)

    # Send notification and wait for reply
    response = await notification_service.notify("Test message", wait_response=True)
    assert response == response_text

@pytest.mark.asyncio
async def test_register_command(notification_service):
    """Test command registration."""
    cmd_name = "test"
    cmd_handler = mock.AsyncMock()
    
    await notification_service.register_command(cmd_name, cmd_handler)
    await notification_service._handle_command(cmd_name, "arg1 arg2")
    
    cmd_handler.assert_called_once_with("arg1 arg2")

@pytest.mark.asyncio
async def test_handle_response(notification_service):
    """Test response handling."""
    msg_id = 123
    response_text = "test response"
    
    # Create future for response
    notification_service._waiting_responses[msg_id] = asyncio.Future()
    
    # Handle response
    notification_service._handle_response(msg_id, response_text)
    
    # Verify response was set
    assert notification_service._waiting_responses[msg_id].result() == response_text

@pytest.mark.asyncio
async def test_response_timeout(notification_service):
    """Test response timeout handling."""
    with pytest.raises(asyncio.TimeoutError):
        await notification_service.notify("Test message", wait_response=True, timeout=0.1)

@pytest.mark.asyncio
async def test_multiple_responses(notification_service):
    """Test handling multiple responses."""
    msg1_id = 123
    msg2_id = 456
    response1 = "response 1"
    response2 = "response 2"

    # Set up mock responses
    mock_msg1 = mock.AsyncMock()
    mock_msg1.message_id = msg1_id
    mock_msg2 = mock.AsyncMock()
    mock_msg2.message_id = msg2_id

    notification_service.bot.send_message.side_effect = [mock_msg1, mock_msg2]

    # Create futures for responses
    notification_service._waiting_responses[msg1_id] = asyncio.Future()
    notification_service._waiting_responses[msg2_id] = asyncio.Future()

    # Start both notifications
    task1 = asyncio.create_task(notification_service.notify("Message 1", wait_response=True))
    task2 = asyncio.create_task(notification_service.notify("Message 2", wait_response=True))

    # Simulate responses
    notification_service._handle_response(msg1_id, response1)
    notification_service._handle_response(msg2_id, response2)

    # Get results
    result1 = await task1
    result2 = await task2

    assert result1 == response1
    assert result2 == response2