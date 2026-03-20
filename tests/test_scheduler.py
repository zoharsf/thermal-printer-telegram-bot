# tests/test_scheduler.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from catprint_bot.scheduler.retry import RetryScheduler


@pytest.fixture
def scheduler():
    return RetryScheduler(
        print_callback=AsyncMock(),
        get_pending_callback=AsyncMock(return_value=[]),
        interval_seconds=1,       # fast for tests
        backoff_seconds=2,
        backoff_threshold=2,
    )


@pytest.mark.asyncio
async def test_scheduler_starts_and_stops(scheduler):
    scheduler.start()
    assert scheduler.is_running
    await asyncio.sleep(0.1)
    await scheduler.stop()
    assert not scheduler.is_running


@pytest.mark.asyncio
async def test_scheduler_pauses_and_resumes(scheduler):
    scheduler.pause()
    assert scheduler.is_paused
    scheduler.resume()
    assert not scheduler.is_paused


@pytest.mark.asyncio
async def test_scheduler_backs_off_after_failures(scheduler):
    scheduler._consecutive_failures = 2  # hits threshold
    scheduler._update_interval()
    assert scheduler._current_interval == 2  # backoff_seconds


@pytest.mark.asyncio
async def test_scheduler_resets_on_success(scheduler):
    scheduler._consecutive_failures = 5
    scheduler._current_interval = 2
    scheduler._on_success()
    assert scheduler._consecutive_failures == 0
    assert scheduler._current_interval == 1  # back to base interval


@pytest.mark.asyncio
async def test_flush_triggers_immediate_cycle(scheduler):
    scheduler._print_callback = AsyncMock()
    scheduler._get_pending_callback = AsyncMock(return_value=[])
    scheduler._consecutive_failures = 5
    scheduler._current_interval = 2

    await scheduler.flush()

    assert scheduler._consecutive_failures == 0
    assert scheduler._current_interval == 1
    scheduler._get_pending_callback.assert_called_once()
