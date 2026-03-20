# tests/test_service.py
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from catprint_bot.service import PrintService
from catprint_bot.printing.driver import PrintResult


@pytest.fixture
def service():
    return PrintService(
        msg_repo=AsyncMock(),
        driver=MagicMock(),
        font_size=14,
    )


@pytest.mark.asyncio
async def test_print_text_message_success(service):
    msg = MagicMock()
    msg.id = 1
    msg.content_type = "text"
    msg.text_content = "Hello!"
    msg.telegram_display_name = "Alice"
    msg.created_at = MagicMock()
    msg.created_at.strftime = MagicMock(return_value="2026-03-20 10:00")

    service._driver.print_pbm = AsyncMock(return_value=PrintResult(success=True))

    result = await service.print_message(msg)

    assert result is True
    service._msg_repo.mark_printing.assert_called_once_with(1)
    service._msg_repo.mark_printed.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_print_text_message_failure(service):
    msg = MagicMock()
    msg.id = 1
    msg.content_type = "text"
    msg.text_content = "Hello!"
    msg.telegram_display_name = "Alice"
    msg.created_at = MagicMock()
    msg.created_at.strftime = MagicMock(return_value="2026-03-20 10:00")

    service._driver.print_pbm = AsyncMock(
        return_value=PrintResult(success=False, error="BLE timeout")
    )

    result = await service.print_message(msg)

    assert result is False
    service._msg_repo.mark_printing.assert_called_once_with(1)
    service._msg_repo.mark_failed.assert_called_once_with(1, reason="BLE timeout")


@pytest.mark.asyncio
async def test_print_image_message(service):
    msg = MagicMock()
    msg.id = 2
    msg.content_type = "image"
    msg.image_path = "/tmp/test.png"
    msg.text_content = None
    msg.telegram_display_name = "Bob"
    msg.created_at = MagicMock()
    msg.created_at.strftime = MagicMock(return_value="2026-03-20 11:00")

    service._driver.print_pbm = AsyncMock(return_value=PrintResult(success=True))

    with patch("catprint_bot.service.render_image") as mock_render:
        mock_render.return_value = Image.new("1", (384, 100), 1)
        result = await service.print_message(msg)

    assert result is True
