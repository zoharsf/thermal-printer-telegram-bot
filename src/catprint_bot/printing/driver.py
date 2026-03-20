"""Async wrapper around cat-printer's sync PrinterDriver.

All BLE operations are run in a thread to avoid blocking the event loop.
The shared asyncio.Lock ensures only one print operation runs at a time.
"""
from __future__ import annotations

import asyncio
import io
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PrintResult:
    success: bool
    error: str | None = None


class PrintDriver:
    def __init__(self, *, address: str, energy: float, lock: asyncio.Lock) -> None:
        self._address = address
        self._energy = energy
        self._lock = lock

    async def print_pbm(self, pbm_data: io.BytesIO) -> PrintResult:
        """Print PBM data to the thermal printer. Acquires the shared lock."""
        async with self._lock:
            try:
                logger.info("Connecting to printer %s...", self._address)
                await asyncio.wait_for(self._do_print(pbm_data), timeout=60.0)
                logger.info("Print complete.")
                return PrintResult(success=True)
            except asyncio.TimeoutError:
                logger.error("Print timed out after 60s — printer unreachable or stuck")
                return PrintResult(success=False, error="Print timed out")
            except Exception as exc:
                logger.error("Print failed: %s", exc, exc_info=True)
                return PrintResult(success=False, error=str(exc))

    async def _do_print(self, pbm_data: io.BytesIO) -> None:
        """Run the sync BLE print operation in a thread."""
        await asyncio.to_thread(self._sync_print, pbm_data)

    def _sync_print(self, pbm_data: io.BytesIO) -> None:
        """Synchronous print via cat-printer. Runs in a worker thread."""
        cat_printer_dir = Path(__file__).parent.parent.parent.parent / "cat-printer"
        if str(cat_printer_dir) not in sys.path:
            sys.path.insert(0, str(cat_printer_dir))

        from printer import PrinterDriver  # type: ignore[import]

        driver = PrinterDriver()
        driver.energy = int(self._energy * 0xFFFF)

        try:
            logger.info("BLE connect start: %s", self._address)
            driver.connect(address=self._address)
            logger.info("BLE connected, printing...")
            driver.print(pbm_data, mode="pbm")
            logger.info("BLE print call returned.")
        finally:
            self._safe_unload(driver)

    @staticmethod
    def _safe_unload(driver) -> None:
        """Disconnect without calling driver.unload() which can crash."""
        try:
            if driver.device is not None:
                driver.loop(driver.device.disconnect())
        except Exception:
            pass

    async def check_connectivity(self) -> bool:
        """Quick check if the printer is reachable. Returns True if connectable."""
        async with self._lock:
            try:
                result = await asyncio.to_thread(self._sync_check)
                return result
            except Exception:
                return False

    def _sync_check(self) -> bool:
        """Try connect + immediate disconnect."""
        cat_printer_dir = Path(__file__).parent.parent.parent.parent / "cat-printer"
        if str(cat_printer_dir) not in sys.path:
            sys.path.insert(0, str(cat_printer_dir))

        from printer import PrinterDriver  # type: ignore[import]

        driver = PrinterDriver()
        try:
            driver.connect(address=self._address)
            self._safe_unload(driver)
            return True
        except Exception:
            self._safe_unload(driver)
            return False
