# tests/test_handlers.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from catprint_bot.bot.handlers import BotHandlers


@pytest.fixture
def deps():
    """Shared mock dependencies for handler tests."""
    return {
        "msg_repo": AsyncMock(),
        "user_repo": AsyncMock(),
        "print_service": AsyncMock(),
        "scheduler": MagicMock(),
        "settings": MagicMock(),
        "admin_user_id": 999,
        "admin_display_name": "TestAdmin",
    }


@pytest.fixture
def handlers(deps):
    return BotHandlers(**deps)


def make_update(user_id=123, username="testuser", first_name="Test", text="hello"):
    """Create a minimal mock Telegram Update."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.effective_user.first_name = first_name
    update.effective_user.last_name = None
    update.message.text = text
    update.message.photo = None
    update.message.reply_text = AsyncMock()
    return update


def make_context():
    return MagicMock()


@pytest.mark.asyncio
async def test_text_message_unauthorized(handlers, deps):
    deps["user_repo"].is_allowed = AsyncMock(return_value=False)
    update = make_update(user_id=456)
    await handlers.handle_message(update, make_context())
    update.message.reply_text.assert_called_once()
    assert "TestAdmin" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_text_message_authorized_print_success(handlers, deps):
    deps["user_repo"].is_allowed = AsyncMock(return_value=True)
    deps["print_service"].print_message = AsyncMock(return_value=True)
    deps["msg_repo"].create = AsyncMock(return_value=MagicMock(id=1))

    update = make_update(user_id=123, text="print this")
    await handlers.handle_message(update, make_context())

    deps["msg_repo"].create.assert_called_once()
    update.message.reply_text.assert_called_once()
    assert "printing" in update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_text_message_authorized_print_fails(handlers, deps):
    deps["user_repo"].is_allowed = AsyncMock(return_value=True)
    deps["print_service"].print_message = AsyncMock(return_value=False)
    deps["msg_repo"].create = AsyncMock(return_value=MagicMock(id=1))

    update = make_update(user_id=123, text="print this")
    await handlers.handle_message(update, make_context())

    assert "queued" in update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_text_too_long_rejected(handlers, deps):
    deps["user_repo"].is_allowed = AsyncMock(return_value=True)
    update = make_update(text="x" * 2001)
    await handlers.handle_message(update, make_context())
    assert "2000" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_admin_status_command(handlers, deps):
    deps["msg_repo"].pending_count = AsyncMock(return_value=3)
    update = make_update(user_id=999)
    update.message.text = "/status"
    await handlers.cmd_status(update, make_context())
    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_non_admin_cannot_use_admin_commands(handlers, deps):
    update = make_update(user_id=456)
    await handlers.cmd_status(update, make_context())
    assert "admin" in update.message.reply_text.call_args[0][0].lower() or \
           "authorized" in update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_flush_command(handlers, deps):
    deps["scheduler"].flush = AsyncMock()
    update = make_update(user_id=999)
    await handlers.cmd_flush(update, make_context())
    deps["scheduler"].flush.assert_called_once()


@pytest.mark.asyncio
async def test_allow_command(handlers, deps):
    deps["user_repo"].add = AsyncMock()
    update = make_update(user_id=999)
    ctx = make_context()
    ctx.args = ["12345"]
    await handlers.cmd_allow(update, ctx)
    deps["user_repo"].add.assert_called_once()


@pytest.mark.asyncio
async def test_remove_command(handlers, deps):
    deps["user_repo"].remove = AsyncMock(return_value=True)
    update = make_update(user_id=999)
    ctx = make_context()
    ctx.args = ["12345"]
    await handlers.cmd_remove(update, ctx)
    deps["user_repo"].remove.assert_called_once()
