# tests/test_repository.py
# Uses db_session fixture from conftest.py
import pytest

from catprint_bot.database.repository import MessageRepository, AllowedUserRepository


# --- MessageRepository ---

@pytest.mark.asyncio
async def test_create_message(db_session):
    repo = MessageRepository(db_session)
    msg = await repo.create(
        telegram_user_id=123,
        telegram_username="alice",
        telegram_display_name="Alice",
        content_type="text",
        text_content="Hello!",
    )
    assert msg.id is not None
    assert msg.status == "pending"


@pytest.mark.asyncio
async def test_get_pending_messages_fifo(db_session):
    repo = MessageRepository(db_session)
    await repo.create(
        telegram_user_id=1, telegram_username=None,
        telegram_display_name="A", content_type="text", text_content="first",
    )
    await repo.create(
        telegram_user_id=2, telegram_username=None,
        telegram_display_name="B", content_type="text", text_content="second",
    )
    pending = await repo.get_pending()
    assert len(pending) == 2
    assert pending[0].text_content == "first"
    assert pending[1].text_content == "second"


@pytest.mark.asyncio
async def test_mark_printed(db_session):
    repo = MessageRepository(db_session)
    msg = await repo.create(
        telegram_user_id=1, telegram_username=None,
        telegram_display_name="A", content_type="text", text_content="test",
    )
    await repo.mark_printing(msg.id)
    await repo.mark_printed(msg.id)
    updated = await repo.get_by_id(msg.id)
    assert updated.status == "printed"
    assert updated.printed_at is not None


@pytest.mark.asyncio
async def test_mark_failed_increments_retry(db_session):
    repo = MessageRepository(db_session)
    msg = await repo.create(
        telegram_user_id=1, telegram_username=None,
        telegram_display_name="A", content_type="text", text_content="test",
    )
    await repo.mark_printing(msg.id)
    await repo.mark_failed(msg.id, reason="BLE timeout")
    updated = await repo.get_by_id(msg.id)
    assert updated.status == "pending"
    assert updated.retry_count == 1
    assert updated.failure_reason == "BLE timeout"


@pytest.mark.asyncio
async def test_get_history(db_session):
    repo = MessageRepository(db_session)
    msg = await repo.create(
        telegram_user_id=1, telegram_username=None,
        telegram_display_name="A", content_type="text", text_content="done",
    )
    await repo.mark_printing(msg.id)
    await repo.mark_printed(msg.id)
    history = await repo.get_history(limit=10)
    assert len(history) == 1
    assert history[0].status == "printed"


@pytest.mark.asyncio
async def test_pending_count(db_session):
    repo = MessageRepository(db_session)
    await repo.create(
        telegram_user_id=1, telegram_username=None,
        telegram_display_name="A", content_type="text", text_content="a",
    )
    assert await repo.pending_count() == 1


# --- AllowedUserRepository ---

@pytest.mark.asyncio
async def test_add_and_check_allowed_user(db_session):
    repo = AllowedUserRepository(db_session)
    await repo.add(telegram_user_id=555, telegram_username="bob", added_by=1)
    assert await repo.is_allowed(555) is True
    assert await repo.is_allowed(999) is False


@pytest.mark.asyncio
async def test_remove_allowed_user(db_session):
    repo = AllowedUserRepository(db_session)
    await repo.add(telegram_user_id=555, telegram_username="bob", added_by=1)
    removed = await repo.remove(555)
    assert removed is True
    assert await repo.is_allowed(555) is False


@pytest.mark.asyncio
async def test_list_allowed_users(db_session):
    repo = AllowedUserRepository(db_session)
    await repo.add(telegram_user_id=1, telegram_username="a", added_by=999)
    await repo.add(telegram_user_id=2, telegram_username="b", added_by=999)
    users = await repo.list_all()
    assert len(users) == 2
