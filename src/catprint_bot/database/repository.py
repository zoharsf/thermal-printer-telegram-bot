from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from catprint_bot.database.models import AllowedUser, Message


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        telegram_user_id: int,
        telegram_username: str | None,
        telegram_display_name: str,
        content_type: str,
        text_content: str | None = None,
        image_path: str | None = None,
    ) -> Message:
        msg = Message(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            telegram_display_name=telegram_display_name,
            content_type=content_type,
            text_content=text_content,
            image_path=image_path,
            status="pending",
        )
        self._session.add(msg)
        await self._session.commit()
        await self._session.refresh(msg)
        return msg

    async def get_by_id(self, message_id: int) -> Message | None:
        return await self._session.get(Message, message_id)

    async def get_pending(self) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.status == "pending")
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def pending_count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Message).where(Message.status == "pending")
        )
        return result.scalar_one()

    async def get_last_printed_at(self) -> datetime | None:
        result = await self._session.execute(
            select(Message.printed_at)
            .where(Message.status == "printed")
            .order_by(Message.printed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history(self, limit: int = 10) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.status == "printed")
            .order_by(Message.printed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_image_path(self, message_id: int, path: str) -> None:
        msg = await self.get_by_id(message_id)
        if msg:
            msg.image_path = path
            await self._session.commit()

    async def mark_printing(self, message_id: int) -> None:
        msg = await self.get_by_id(message_id)
        if msg:
            msg.status = "printing"
            await self._session.commit()

    async def mark_printed(self, message_id: int) -> None:
        msg = await self.get_by_id(message_id)
        if msg:
            msg.status = "printed"
            msg.printed_at = datetime.now(timezone.utc)
            msg.failure_reason = None
            await self._session.commit()

    async def mark_failed(self, message_id: int, *, reason: str) -> None:
        msg = await self.get_by_id(message_id)
        if msg:
            msg.status = "pending"
            msg.retry_count += 1
            msg.failure_reason = reason
            await self._session.commit()


class AllowedUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        telegram_user_id: int,
        telegram_username: str | None,
        added_by: int,
    ) -> AllowedUser:
        user = AllowedUser(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            added_by=added_by,
        )
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update_username(self, telegram_user_id: int, username: str | None) -> None:
        user = await self._session.get(AllowedUser, telegram_user_id)
        if user and user.telegram_username != username:
            user.telegram_username = username
            await self._session.commit()

    async def remove(self, telegram_user_id: int) -> bool:
        user = await self._session.get(AllowedUser, telegram_user_id)
        if user:
            await self._session.delete(user)
            await self._session.commit()
            return True
        return False

    async def is_allowed(self, telegram_user_id: int) -> bool:
        user = await self._session.get(AllowedUser, telegram_user_id)
        return user is not None

    async def list_all(self) -> list[AllowedUser]:
        result = await self._session.execute(
            select(AllowedUser).order_by(AllowedUser.added_at.asc())
        )
        return list(result.scalars().all())
