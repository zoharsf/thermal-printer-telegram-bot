from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Telegram
    telegram_bot_token: str
    admin_telegram_user_id: int
    admin_display_name: str

    # Printer
    printer_address: str
    printer_energy: float = 0.75
    printer_font_size: int = 14

    # Retry
    retry_interval_seconds: int = 600
    retry_backoff_seconds: int = 1800
    retry_backoff_threshold: int = 3

    # Paths
    data_dir: Path = Path("/data")
    database_url: str = "sqlite+aiosqlite:////data/catprint.db"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"
