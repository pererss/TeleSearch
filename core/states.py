"""State-машина: ожидание текстового ввода от пользователя.

Значение: кортеж (режим, payload).
Режимы: "query", "support_msg", "admin_find", "admin_block",
        "admin_reply", "admin_broadcast", "admin_text", "admin_setting".
"""
from __future__ import annotations

import time
from typing import Any


class States:
    def __init__(self) -> None:
        self._store: dict[int, tuple] = {}
        self._ts: dict[int, float] = {}

    def set(self, user_id: int, *value: Any) -> None:
        self._store[user_id] = tuple(value)
        self._ts[user_id] = time.monotonic()

    def get(self, user_id: int) -> tuple | None:
        val = self._store.get(user_id)
        if val is None:
            return None
        # аварийный таймаут ввода — 10 минут
        if time.monotonic() - self._ts.get(user_id, 0) > 600:
            self.clear(user_id)
            return None
        return val

    def clear(self, user_id: int) -> None:
        self._store.pop(user_id, None)
        self._ts.pop(user_id, None)


# Кнопка «Отмена» доступна в любом ожидании ввода
CANCEL = "cancel"
CANCEL_LABEL = "❌ Отмена"


def cancel_keyboard() -> Any:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[InlineKeyboardButton(CANCEL_LABEL, callback_data=CANCEL)]])