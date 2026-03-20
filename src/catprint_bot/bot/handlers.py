"""Telegram bot command and message handlers."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from catprint_bot.bot.auth import is_authorized
from catprint_bot.database.repository import AllowedUserRepository, MessageRepository

logger = logging.getLogger(__name__)

_MAX_TEXT_LENGTH = 2000
_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


class BotHandlers:
    def __init__(
        self,
        *,
        msg_repo: MessageRepository,
        user_repo: AllowedUserRepository,
        print_service,
        scheduler,
        settings,
        admin_user_id: int,
        admin_display_name: str,
    ) -> None:
        self._msg_repo = msg_repo
        self._user_repo = user_repo
        self._print_service = print_service
        self._scheduler = scheduler
        self._settings = settings
        self._admin_user_id = admin_user_id
        self._admin_display_name = admin_display_name

    def _is_admin(self, user_id: int) -> bool:
        return user_id == self._admin_user_id

    def _display_name(self, user) -> str:
        parts = [user.first_name or ""]
        if user.last_name:
            parts.append(user.last_name)
        return " ".join(parts).strip() or "Unknown"

    # --- Message handlers ---

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        authorized = await is_authorized(
            user_id=user.id,
            admin_user_id=self._admin_user_id,
            allowed_repo=self._user_repo,
        )
        if not authorized:
            await update.message.reply_text(
                f"Sorry, you're not authorized to print. Ask {self._admin_display_name} to add you."
            )
            return

        await self._user_repo.update_username(user.id, user.username)

        if update.message.photo:
            await self._handle_image(update, context)
        elif update.message.text:
            await self._handle_text(update, context)
        else:
            await update.message.reply_text("I can only print text and images.")

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text
        if len(text) > _MAX_TEXT_LENGTH:
            await update.message.reply_text(
                f"Message too long — max {_MAX_TEXT_LENGTH} characters."
            )
            return

        user = update.effective_user
        msg = await self._msg_repo.create(
            telegram_user_id=user.id,
            telegram_username=user.username,
            telegram_display_name=self._display_name(user),
            content_type="text",
            text_content=text,
        )

        success = await self._print_service.print_message(msg)
        if success:
            await update.message.reply_text("Message received, printing!")
        else:
            await update.message.reply_text("Message queued, printer offline.")

    async def _handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        photo = update.message.photo[-1]
        if photo.file_size and photo.file_size > _MAX_IMAGE_SIZE:
            await update.message.reply_text("Image too large — max 5 MB.")
            return

        try:
            file = await context.bot.get_file(photo.file_id)
            image_bytes = await file.download_as_bytearray()
        except Exception as exc:
            logger.error("Failed to download image: %s", exc)
            await update.message.reply_text("Failed to download your image, please resend.")
            return

        try:
            from PIL import Image as PILImage
            import io as _io
            img = PILImage.open(_io.BytesIO(bytes(image_bytes)))
            if img.format not in ("JPEG", "PNG", "WEBP"):
                await update.message.reply_text("Unsupported image format. Please send JPEG, PNG, or WebP.")
                return
        except Exception:
            await update.message.reply_text("Could not read image. Please send JPEG, PNG, or WebP.")
            return

        self._settings.images_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        import uuid
        tmp_name = f"tmp_{uuid.uuid4().hex}.png"
        tmp_path = self._settings.images_dir / tmp_name
        tmp_path.write_bytes(bytes(image_bytes))

        user = update.effective_user
        msg = await self._msg_repo.create(
            telegram_user_id=user.id,
            telegram_username=user.username,
            telegram_display_name=self._display_name(user),
            content_type="image",
        )

        final_path = self._settings.images_dir / f"{msg.id}_{ts}.png"
        tmp_path.rename(final_path)
        await self._msg_repo.update_image_path(msg.id, str(final_path))

        success = await self._print_service.print_message(msg)
        if success:
            await update.message.reply_text("Message received, printing!")
        else:
            await update.message.reply_text("Message queued, printer offline.")

    # --- Admin commands ---

    async def _require_admin(self, update: Update) -> bool:
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("This command is only available to the admin.")
            return False
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._is_admin(update.effective_user.id):
            await update.message.reply_text(
                "Welcome! You're the admin.\n\n"
                "Commands:\n"
                "/status — printer status & queue\n"
                "/flush — print all queued messages now\n"
                "/queue — view pending messages (with images)\n"
                "/reprint <id> — reprint a message by ID\n"
                "/history [n] — recent prints\n"
                "/allow <user_id> — add user\n"
                "/remove <user_id> — remove user\n"
                "/allowlist — list allowed users\n"
                "/pause — pause auto-printing\n"
                "/resume — resume auto-printing"
            )
        else:
            await update.message.reply_text(
                "Hi! Send me a text message or image and I'll print it."
            )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        pending = await self._msg_repo.pending_count()
        last_print = await self._msg_repo.get_last_printed_at()
        last_print_str = last_print.strftime("%Y-%m-%d %H:%M") if last_print else "never"
        paused = self._scheduler.is_paused
        failures = self._scheduler.consecutive_failures
        await update.message.reply_text(
            f"Pending messages: {pending}\n"
            f"Last successful print: {last_print_str}\n"
            f"Scheduler: {'paused' if paused else 'running'}\n"
            f"Consecutive failures: {failures}"
        )

    async def cmd_flush(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        await update.message.reply_text("Flushing queue...")
        await self._scheduler.flush()
        await update.message.reply_text("Flush complete.")

    async def cmd_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        pending = await self._msg_repo.get_pending()
        if not pending:
            await update.message.reply_text("No pending messages.")
            return
        from pathlib import Path
        for msg in pending[:20]:
            name = msg.telegram_display_name
            if msg.content_type == "image" and msg.image_path:
                image_file = Path(msg.image_path)
                if image_file.exists():
                    with open(image_file, "rb") as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=f"*#{msg.id}* from {name}",
                            parse_mode="Markdown",
                        )
                else:
                    await update.message.reply_text(
                        f"*#{msg.id}* from {name}: \\[image file missing\\]",
                        parse_mode="Markdown",
                    )
            else:
                preview = (msg.text_content or "")[:50]
                await update.message.reply_text(
                    f"*#{msg.id}* from {name}: {preview}",
                    parse_mode="Markdown",
                )

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        limit = 10
        if context.args:
            try:
                limit = int(context.args[0])
            except ValueError:
                pass
        history = await self._msg_repo.get_history(limit=limit)
        if not history:
            await update.message.reply_text("No print history yet.")
            return
        lines = []
        for msg in history:
            preview = (msg.text_content or "[image]")[:50]
            ts = msg.printed_at.strftime("%Y-%m-%d %H:%M") if msg.printed_at else "?"
            lines.append(f"#{msg.id} {ts} — {msg.telegram_display_name}: {preview}")
        await update.message.reply_text("\n".join(lines))

    async def cmd_allow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /allow <telegram_user_id>")
            return
        try:
            user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("User ID must be a number.")
            return
        await self._user_repo.add(
            telegram_user_id=user_id,
            telegram_username=None,
            added_by=update.effective_user.id,
        )
        await update.message.reply_text(f"User {user_id} added to allowlist.")

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /remove <telegram_user_id>")
            return
        try:
            user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("User ID must be a number.")
            return
        removed = await self._user_repo.remove(user_id)
        if removed:
            await update.message.reply_text(f"User {user_id} removed from allowlist.")
        else:
            await update.message.reply_text(f"User {user_id} was not in the allowlist.")

    async def cmd_allowlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        users = await self._user_repo.list_all()
        if not users:
            await update.message.reply_text("Allowlist is empty.")
            return
        lines = []
        for u in users:
            username = f"@{u.telegram_username}" if u.telegram_username else "(no username)"
            lines.append(f"• {username} — ID: {u.telegram_user_id}")
        await update.message.reply_text("Allowed users:\n" + "\n".join(lines))

    async def cmd_reprint(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /reprint <message_id>")
            return
        try:
            message_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Message ID must be a number.")
            return
        msg = await self._msg_repo.get_by_id(message_id)
        if not msg:
            await update.message.reply_text(f"Message #{message_id} not found.")
            return
        await update.message.reply_text(f"Reprinting message #{message_id}...")
        success = await self._print_service.print_message(msg)
        if success:
            await update.message.reply_text(f"Message #{message_id} reprinted!")
        else:
            await update.message.reply_text(f"Failed to reprint #{message_id} — queued for retry.")

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        self._scheduler.pause()
        await update.message.reply_text("Auto-printing paused. Messages will still be queued.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_admin(update):
            return
        self._scheduler.resume()
        await update.message.reply_text("Auto-printing resumed.")
