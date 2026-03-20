"""Application entrypoint — starts all subsystems."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
import json as _json

import uvicorn
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from catprint_bot.api.health import create_health_app
from catprint_bot.bot.handlers import BotHandlers
from catprint_bot.config import Settings
from catprint_bot.database.repository import AllowedUserRepository, MessageRepository
from catprint_bot.database.session import close_db, create_tables, get_session, init_db
from catprint_bot.printing.driver import PrintDriver
from catprint_bot.scheduler.retry import RetryScheduler
from catprint_bot.service import PrintService


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_data["exception"] = str(record.exc_info[1])
        return _json.dumps(log_data)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logging.getLogger("telegram").setLevel(logging.DEBUG)
logging.getLogger("telegram.ext.Updater").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


async def run() -> None:
    settings = Settings()

    # Database
    init_db(settings)
    await create_tables()
    settings.images_dir.mkdir(parents=True, exist_ok=True)

    # Get a long-lived session for the bot
    session_gen = get_session()
    session = await session_gen.__anext__()

    msg_repo = MessageRepository(session)
    user_repo = AllowedUserRepository(session)

    # Print driver with shared lock
    print_lock = asyncio.Lock()
    driver = PrintDriver(
        address=settings.printer_address,
        energy=settings.printer_energy,
        lock=print_lock,
    )
    print_service = PrintService(
        msg_repo=msg_repo,
        driver=driver,
        font_size=settings.printer_font_size,
    )

    # Retry scheduler
    scheduler = RetryScheduler(
        print_callback=print_service.print_message,
        get_pending_callback=msg_repo.get_pending,
        interval_seconds=settings.retry_interval_seconds,
        backoff_seconds=settings.retry_backoff_seconds,
        backoff_threshold=settings.retry_backoff_threshold,
    )

    # Bot handlers
    handlers = BotHandlers(
        msg_repo=msg_repo,
        user_repo=user_repo,
        print_service=print_service,
        scheduler=scheduler,
        settings=settings,
        admin_user_id=settings.admin_telegram_user_id,
        admin_display_name=settings.admin_display_name,
    )

    # Telegram bot application
    # PTB v21 uses separate HTTP connections for regular calls and getUpdates.
    # The getUpdates long-poll API timeout is 10s, so read_timeout must exceed it.
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0)
    get_updates_request = HTTPXRequest(connect_timeout=30.0, read_timeout=15.0)
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .request(request)
        .get_updates_request(get_updates_request)
        .build()
    )

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("status", handlers.cmd_status))
    app.add_handler(CommandHandler("flush", handlers.cmd_flush))
    app.add_handler(CommandHandler("queue", handlers.cmd_queue))
    app.add_handler(CommandHandler("history", handlers.cmd_history))
    app.add_handler(CommandHandler("allow", handlers.cmd_allow))
    app.add_handler(CommandHandler("remove", handlers.cmd_remove))
    app.add_handler(CommandHandler("allowlist", handlers.cmd_allowlist))
    app.add_handler(CommandHandler("pause", handlers.cmd_pause))
    app.add_handler(CommandHandler("resume", handlers.cmd_resume))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handlers.handle_message))

    # FastAPI
    health_app = create_health_app(msg_repo=msg_repo, scheduler=scheduler)
    config = uvicorn.Config(health_app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    async def error_handler(update, context) -> None:
        logger.error("PTB error: %s", context.error, exc_info=context.error)

    app.add_error_handler(error_handler)

    # Graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_signal(sig, frame):
        logger.info("Received %s, shutting down...", signal.Signals(sig).name)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Start everything
    scheduler.start()
    logger.info("Starting catprint-bot...")

    async with app:
        await app.start()
        await app.updater.start_polling()

        # Run FastAPI server in background
        server_task = asyncio.create_task(server.serve())

        # Wait for shutdown signal
        await shutdown_event.wait()

        logger.info("Shutting down...")
        await app.updater.stop()
        await app.stop()
        await scheduler.stop()
        server.should_exit = True
        await server_task
        await close_db()

    logger.info("Shutdown complete.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
