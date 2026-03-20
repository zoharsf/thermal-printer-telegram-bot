# tests/test_models.py
# Uses db_session fixture from conftest.py
import pytest
from sqlalchemy import select

from catprint_bot.database.models import Message, AllowedUser


@pytest.mark.asyncio
async def test_create_text_message(db_session):
    msg = Message(
        telegram_user_id=12345,
        telegram_username="testuser",
        telegram_display_name="Test User",
        content_type="text",
        text_content="Hello printer!",
        status="pending",
    )
    db_session.add(msg)
    await db_session.commit()

    result = await db_session.execute(select(Message))
    saved = result.scalar_one()

    assert saved.telegram_user_id == 12345
    assert saved.content_type == "text"
    assert saved.text_content == "Hello printer!"
    assert saved.status == "pending"
    assert saved.retry_count == 0
    assert saved.created_at is not None
    assert saved.printed_at is None


@pytest.mark.asyncio
async def test_create_image_message(db_session):
    msg = Message(
        telegram_user_id=12345,
        telegram_username="testuser",
        telegram_display_name="Test User",
        content_type="image",
        image_path="/data/images/1_20260320.png",
        status="pending",
    )
    db_session.add(msg)
    await db_session.commit()

    result = await db_session.execute(select(Message))
    saved = result.scalar_one()
    assert saved.content_type == "image"
    assert saved.image_path == "/data/images/1_20260320.png"


@pytest.mark.asyncio
async def test_create_allowed_user(db_session):
    user = AllowedUser(
        telegram_user_id=67890,
        telegram_username="friend1",
        added_by=12345,
    )
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(AllowedUser))
    saved = result.scalar_one()
    assert saved.telegram_user_id == 67890
    assert saved.added_by == 12345
    assert saved.added_at is not None
