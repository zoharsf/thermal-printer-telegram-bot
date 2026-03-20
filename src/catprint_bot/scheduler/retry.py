"""Background retry scheduler for pending print jobs.

Periodically checks for pending messages and attempts to print them.
Backs off after consecutive failures, resets on success.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class RetryScheduler:
    def __init__(
        self,
        *,
        print_callback: Callable,
        get_pending_callback: Callable,
        interval_seconds: int = 600,
        backoff_seconds: int = 1800,
        backoff_threshold: int = 3,
    ) -> None:
        self._print_callback = print_callback
        self._get_pending_callback = get_pending_callback
        self._base_interval = interval_seconds
        self._backoff_interval = backoff_seconds
        self._backoff_threshold = backoff_threshold

        self._current_interval = interval_seconds
        self._consecutive_failures = 0
        self._paused = False
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Retry scheduler started (interval=%ds)", self._current_interval)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Retry scheduler stopped")

    def pause(self) -> None:
        self._paused = True
        logger.info("Retry scheduler paused")

    def resume(self) -> None:
        self._paused = False
        logger.info("Retry scheduler resumed")

    async def flush(self) -> None:
        """Reset backoff and run one cycle immediately."""
        self._consecutive_failures = 0
        self._current_interval = self._base_interval
        logger.info("Flush triggered — running immediate retry cycle")
        await self._run_cycle()

    async def _run_loop(self) -> None:
        while True:
            await asyncio.sleep(self._current_interval)
            if self._paused:
                logger.debug("Scheduler paused, skipping cycle")
                continue
            await self._run_cycle()

    async def _run_cycle(self) -> None:
        pending = await self._get_pending_callback()
        if not pending:
            logger.debug("No pending messages")
            return

        logger.info("Retrying %d pending message(s)", len(pending))
        for msg in pending:
            success = await self._print_callback(msg)
            if success:
                self._on_success()
            else:
                self._on_failure()
                break  # stop trying if printer is down

    def _on_success(self) -> None:
        self._consecutive_failures = 0
        self._current_interval = self._base_interval

    def _on_failure(self) -> None:
        self._consecutive_failures += 1
        self._update_interval()

    def _update_interval(self) -> None:
        if self._consecutive_failures >= self._backoff_threshold:
            self._current_interval = self._backoff_interval
            logger.warning(
                "Backed off to %ds after %d consecutive failures",
                self._backoff_interval,
                self._consecutive_failures,
            )
        else:
            self._current_interval = self._base_interval
