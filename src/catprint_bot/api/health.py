"""FastAPI health check and metrics endpoints."""
from __future__ import annotations

import logging
import os
import shutil

from fastapi import FastAPI

logger = logging.getLogger(__name__)

_DISK_WARNING_THRESHOLD = 90.0


def _get_disk_usage_percent() -> float:
    disk = shutil.disk_usage("/data") if os.path.exists("/data") else shutil.disk_usage("/")
    return round((disk.used / disk.total) * 100, 1)


def create_health_app(*, msg_repo, scheduler) -> FastAPI:
    app = FastAPI(title="thermal-printer-telegram-bot", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health():
        disk_pct = _get_disk_usage_percent()
        if disk_pct >= _DISK_WARNING_THRESHOLD:
            logger.warning("Disk usage at %.1f%% — consider cleaning old images", disk_pct)
            return {"status": "warning", "reason": f"disk usage {disk_pct}%"}
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics():
        pending = await msg_repo.pending_count()
        disk_pct = _get_disk_usage_percent()
        if disk_pct >= _DISK_WARNING_THRESHOLD:
            logger.warning("Disk usage at %.1f%%", disk_pct)
        return {
            "pending_messages": pending,
            "scheduler_paused": scheduler.is_paused,
            "consecutive_failures": scheduler.consecutive_failures,
            "disk_usage_percent": disk_pct,
        }

    return app
