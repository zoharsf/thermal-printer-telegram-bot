import os
import pytest
from catprint_bot.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("ADMIN_TELEGRAM_USER_ID", "999")
    monkeypatch.setenv("ADMIN_DISPLAY_NAME", "TestAdmin")
    monkeypatch.setenv("PRINTER_ADDRESS", "AA:BB:CC:DD:EE:FF")

    settings = Settings()

    assert settings.telegram_bot_token == "test-token-123"
    assert settings.admin_telegram_user_id == 999
    assert settings.admin_display_name == "TestAdmin"
    assert settings.printer_address == "AA:BB:CC:DD:EE:FF"


def test_settings_defaults():
    """Defaults for optional fields should be sensible."""
    monkeypatch_env = {
        "TELEGRAM_BOT_TOKEN": "tok",
        "ADMIN_TELEGRAM_USER_ID": "1",
        "ADMIN_DISPLAY_NAME": "Admin",
        "PRINTER_ADDRESS": "AA:BB:CC:DD:EE:FF",
    }
    with pytest.MonkeyPatch.context() as mp:
        for k, v in monkeypatch_env.items():
            mp.setenv(k, v)
        settings = Settings()

    assert settings.printer_energy == 0.75
    assert settings.printer_font_size == 14
    assert settings.retry_interval_seconds == 600
    assert settings.retry_backoff_seconds == 1800
    assert settings.retry_backoff_threshold == 3


def test_settings_missing_required_raises():
    """Must raise if required env vars are missing."""
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        mp.delenv("ADMIN_TELEGRAM_USER_ID", raising=False)
        mp.delenv("ADMIN_DISPLAY_NAME", raising=False)
        mp.delenv("PRINTER_ADDRESS", raising=False)
        with pytest.raises(Exception):
            Settings()
