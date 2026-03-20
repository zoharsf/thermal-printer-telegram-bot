"""Authorization checks for Telegram users."""
from __future__ import annotations

from catprint_bot.database.repository import AllowedUserRepository


async def is_authorized(
    *,
    user_id: int,
    admin_user_id: int,
    allowed_repo: AllowedUserRepository,
) -> bool:
    """Check if a Telegram user is authorized to print.

    The admin is always authorized (not stored in the DB).
    """
    if user_id == admin_user_id:
        return True
    return await allowed_repo.is_allowed(user_id)
