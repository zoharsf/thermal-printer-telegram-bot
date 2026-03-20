"""Print service — orchestrates rendering, printing, and DB updates."""
from __future__ import annotations

import logging

from catprint_bot.database.models import Message
from catprint_bot.database.repository import MessageRepository
from catprint_bot.printing.driver import PrintDriver
from catprint_bot.printing.renderer import (
    PAPER_WIDTH,
    compose,
    image_to_pbm,
    render_image,
    render_text,
)

logger = logging.getLogger(__name__)


class PrintService:
    def __init__(
        self,
        *,
        msg_repo: MessageRepository,
        driver: PrintDriver,
        font_size: int = 14,
    ) -> None:
        self._msg_repo = msg_repo
        self._driver = driver
        self._font_size = font_size

    async def print_message(self, msg: Message) -> bool:
        """Render and print a message. Returns True on success."""
        await self._msg_repo.mark_printing(msg.id)

        try:
            header_text = f"{msg.telegram_display_name}  {msg.created_at.strftime('%Y-%m-%d %H:%M')}"
            header_img = render_text(header_text, self._font_size, PAPER_WIDTH)

            if msg.content_type == "image" and msg.image_path:
                body_img = render_image(msg.image_path, PAPER_WIDTH)
            else:
                body_img = render_text(msg.text_content or "", self._font_size, PAPER_WIDTH)

            final = compose(body_img, header=header_img)
            pbm = image_to_pbm(final)

        except Exception as exc:
            logger.error("Rendering failed for message %d: %s", msg.id, exc)
            await self._msg_repo.mark_failed(msg.id, reason=f"Render error: {exc}")
            return False

        logger.info("Rendering complete for message %d, sending to printer...", msg.id)
        result = await self._driver.print_pbm(pbm)

        if result.success:
            await self._msg_repo.mark_printed(msg.id)
            logger.info("Printed message %d from %s", msg.id, msg.telegram_display_name)
            return True
        else:
            await self._msg_repo.mark_failed(msg.id, reason=result.error or "Unknown error")
            logger.warning("Failed to print message %d: %s", msg.id, result.error)
            return False
