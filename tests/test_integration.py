# tests/test_integration.py
# Uses db_session fixture from conftest.py
"""Integration smoke test — full flow without BLE or Telegram."""
from unittest.mock import AsyncMock

import pytest

from catprint_bot.database.repository import AllowedUserRepository, MessageRepository
from catprint_bot.printing.driver import PrintResult
from catprint_bot.service import PrintService


@pytest.mark.asyncio
async def test_full_print_flow(db_session):
    """Message created → printed → marked as printed in DB."""
    msg_repo = MessageRepository(db_session)
    driver = AsyncMock()
    driver.print_pbm = AsyncMock(return_value=PrintResult(success=True))

    service = PrintService(msg_repo=msg_repo, driver=driver, font_size=14)

    # Create a message
    msg = await msg_repo.create(
        telegram_user_id=123,
        telegram_username="alice",
        telegram_display_name="Alice",
        content_type="text",
        text_content="Integration test message!",
    )

    # Print it
    result = await service.print_message(msg)
    assert result is True

    # Verify DB state
    updated = await msg_repo.get_by_id(msg.id)
    assert updated.status == "printed"
    assert updated.printed_at is not None


@pytest.mark.asyncio
async def test_full_retry_flow(db_session):
    """Message fails → stays pending → retry picks it up → prints successfully."""
    msg_repo = MessageRepository(db_session)

    # First attempt fails
    fail_driver = AsyncMock()
    fail_driver.print_pbm = AsyncMock(
        return_value=PrintResult(success=False, error="BLE down")
    )
    fail_service = PrintService(msg_repo=msg_repo, driver=fail_driver, font_size=14)

    msg = await msg_repo.create(
        telegram_user_id=456,
        telegram_username="bob",
        telegram_display_name="Bob",
        content_type="text",
        text_content="Retry test",
    )

    result = await fail_service.print_message(msg)
    assert result is False

    updated = await msg_repo.get_by_id(msg.id)
    assert updated.status == "pending"
    assert updated.retry_count == 1

    # Retry succeeds
    ok_driver = AsyncMock()
    ok_driver.print_pbm = AsyncMock(return_value=PrintResult(success=True))
    ok_service = PrintService(msg_repo=msg_repo, driver=ok_driver, font_size=14)

    pending = await msg_repo.get_pending()
    assert len(pending) == 1

    result = await ok_service.print_message(pending[0])
    assert result is True

    final = await msg_repo.get_by_id(msg.id)
    assert final.status == "printed"


@pytest.mark.asyncio
async def test_authorization_flow(db_session):
    """Allowed users can print, others cannot."""
    user_repo = AllowedUserRepository(db_session)

    assert await user_repo.is_allowed(999) is False

    await user_repo.add(telegram_user_id=999, telegram_username="friend", added_by=1)
    assert await user_repo.is_allowed(999) is True

    await user_repo.remove(999)
    assert await user_repo.is_allowed(999) is False
