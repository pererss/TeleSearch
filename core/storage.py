"""Минимальное постоянное хранилище на JSON-файлах (без отдельной БД).

Нужно только для: пользователей, статистики, редактируемых текстов,
настроек, тикетов поддержки и жалоб.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

_file_locks: dict[str, asyncio.Lock] = {}


def _lock_for(path: Path) -> asyncio.Lock:
    key = str(path)
    if key not in _file_locks:
        _file_locks[key] = asyncio.Lock()
    return _file_locks[key]


async def json_load(path: Path, default: Any) -> Any:
    """Читает JSON-файл, создавая default, если файла нет."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return copy.deepcopy(default)
    try:
        async with _lock_for(path):
            data = await asyncio.to_thread(path.read_text, encoding="utf-8")
        return json.loads(data)
    except (json.JSONDecodeError, OSError):
        return copy.deepcopy(default)


async def json_save(path: Path, data: Any) -> None:
    """Атомарная запись JSON (temp + rename), чтобы не повредить файл."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=1)
    async with _lock_for(path):
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


class Store:
    """In-memory состояние бота + периодическое сохранение в JSON."""

    FILES = ("users", "stats", "texts", "settings", "tickets", "complaints")

    def __init__(self, data_dir: Path, texts_defaults: dict, settings_defaults: dict) -> None:
        self.dir: Path = data_dir
        self._texts_defaults = texts_defaults
        self._settings_defaults = settings_defaults

        self.users: dict = {}
        self.stats: dict = {}
        self.texts: dict = {}
        self.settings: dict = {}
        self.tickets: list = []
        self.complaints: list = []

    async def load_all(self) -> None:
        async def load(name: str) -> Any:
            return await json_load(self.dir / f"{name}.json", None)

        self.users = (await load("users")) or {}
        self.stats = (await load("stats")) or _new_stats()
        raw_texts = await load("texts")
        self.texts = {**self._texts_defaults, **(raw_texts or {})}
        raw_settings = await load("settings")
        self.settings = {**self._settings_defaults, **(raw_settings or {})}
        if not isinstance(self.settings.get("hidden_categories"), list):
            self.settings["hidden_categories"] = []
        self.tickets = (await load("tickets")) or []
        self.complaints = (await load("complaints")) or []
        await self.save_all()

    async def save_all(self) -> None:
        await asyncio.gather(
            json_save(self.dir / "users.json", self.users),
            json_save(self.dir / "stats.json", self.stats),
            json_save(self.dir / "texts.json", self.texts),
            json_save(self.dir / "settings.json", self.settings),
            json_save(self.dir / "tickets.json", self.tickets),
            json_save(self.dir / "complaints.json", self.complaints),
        )


def _new_stats() -> dict:
    return {
        "queries": {},        # запрос -> счётчик
        "categories": {},     # категория -> счётчик
        "types": {"chat": 0, "channel": 0, "bot": 0},  # открытые в результатах
        "by_date": {},        # "YYYY-MM-DD" -> {"searches": n, "new_users": n}
        "errors": [],         # {"ts": unix, "kind": str, "detail": str}, ring
        "errors_total": 0,
        "tickets_open": 0,
        "tickets_total": 0,
        "complaints_open": 0,
        "complaints_total": 0,
    }