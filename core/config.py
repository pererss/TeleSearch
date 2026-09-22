"""Конфигурация проекта: переменные окружения и константы."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Корень проекта — папка, где лежит этот файл (core/config.py -> ../../)
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Config:
    """Все настройки бота."""

    def __init__(self) -> None:
        self.bot_token: str = os.getenv("BOT_TOKEN", "").strip()
        self.admin_id: int = _int_env("ADMIN_ID", 5434264152)
        self.tgden_base: str = os.getenv("TGDEN_BASE_URL", "https://tgden.com").rstrip("/")
        self.search_limit: int = _int_env("SEARCH_LIMIT", 3)
        self.search_window: int = _int_env("SEARCH_WINDOW", 60)
        self.result_page_size: int = _int_env("RESULT_PAGE_SIZE", 5)
        self.fetch_pages: int = _int_env("FETCH_PAGES", 1)
        self.log_to_file: bool = os.getenv("LOG_TO_FILE", "1") not in ("0", "false", "False")

        self.data_dir: Path = BASE_DIR / "data"

    @property
    def token_ok(self) -> bool:
        return bool(self.bot_token) and ":" in self.bot_token


config = Config()