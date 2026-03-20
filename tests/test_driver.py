# tests/test_driver.py
import asyncio
import io
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from catprint_bot.printing.driver import PrintDriver


@pytest.fixture
def mock_cat_printer():
    driver = MagicMock()
    driver.device = MagicMock()
    driver.loop = MagicMock()
    return driver


@pytest.mark.asyncio
async def test_print_message_acquires_lock():
    """Print operations must be serialized."""
    lock = asyncio.Lock()
    driver = PrintDriver(address="AA:BB:CC:DD:EE:FF", energy=0.75, lock=lock)

    call_order = []

    async def fake_print(pbm_data):
        call_order.append("start")
        await asyncio.sleep(0.05)
        call_order.append("end")

    with patch.object(driver, "_do_print", side_effect=fake_print):
        pbm = io.BytesIO(b"P4 data")
        await asyncio.gather(
            driver.print_pbm(pbm),
            driver.print_pbm(pbm),
        )

    # With lock, operations are serialized: start, end, start, end
    assert call_order == ["start", "end", "start", "end"]


@pytest.mark.asyncio
async def test_print_returns_success_on_ok():
    lock = asyncio.Lock()
    driver = PrintDriver(address="AA:BB:CC:DD:EE:FF", energy=0.75, lock=lock)

    with patch.object(driver, "_do_print", new_callable=AsyncMock):
        result = await driver.print_pbm(io.BytesIO(b"data"))

    assert result.success is True
    assert result.error is None


@pytest.mark.asyncio
async def test_print_returns_failure_on_exception():
    lock = asyncio.Lock()
    driver = PrintDriver(address="AA:BB:CC:DD:EE:FF", energy=0.75, lock=lock)

    with patch.object(
        driver, "_do_print", new_callable=AsyncMock, side_effect=Exception("BLE timeout")
    ):
        result = await driver.print_pbm(io.BytesIO(b"data"))

    assert result.success is False
    assert "BLE timeout" in result.error
