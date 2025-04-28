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
    notification_service.bot.get_updates = AsyncMock(return_value=[
        MagicMock(
            message=MagicMock(
                reply_to_message=MagicMock(message_id=123),
                text="user response"
            )
        )
    ])

    response = await notification_service.notify("test message", wait_response=True)
    assert response == "user response"


@pytest.mark.asyncio
async def test_response_timeout(notification_service):
    """Test notification response timeout."""
    notification_service.bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))
    notification_service.bot.get_updates = AsyncMock(return_value=[])

    response = await notification_service.notify("test message", wait_response=True, response_timeout=0.1)
    assert response is None


@pytest.mark.asyncio
async def test_multiple_responses(notification_service):
    """Test handling multiple responses."""
    notification_service.bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))
    notification_service.bot.get_updates = AsyncMock(side_effect=[
        [MagicMock(
            message=MagicMock(
                reply_to_message=MagicMock(message_id=123),
                text="response 1"
            )
        )],
        [MagicMock(
            message=MagicMock(
                reply_to_message=MagicMock(message_id=123),
                text="response 2"
            )
        )]
    ])

    responses = []
    responses.append(await notification_service.notify("message 1", wait_response=True))
    responses.append(await notification_service.notify("message 2", wait_response=True))

    assert responses == ["response 1", "response 2"]