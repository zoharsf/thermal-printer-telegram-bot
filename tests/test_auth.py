# tests/test_auth.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from catprint_bot.bot.auth import is_authorized


@pytest.mark.asyncio
async def test_admin_is_always_authorized():
    result = await is_authorized(
        user_id=999,
        admin_user_id=999,
        allowed_repo=AsyncMock(),
    )
    assert result is True


@pytest.mark.asyncio
async def test_allowed_user_is_authorized():
    repo = AsyncMock()
    repo.is_allowed = AsyncMock(return_value=True)
    result = await is_authorized(
        user_id=123,
        admin_user_id=999,
        allowed_repo=repo,
    )
    assert result is True
    repo.is_allowed.assert_called_once_with(123)


@pytest.mark.asyncio
async def test_unknown_user_is_not_authorized():
    repo = AsyncMock()
    repo.is_allowed = AsyncMock(return_value=False)
    result = await is_authorized(
        user_id=456,
        admin_user_id=999,
        allowed_repo=repo,
    )
    assert result is False
