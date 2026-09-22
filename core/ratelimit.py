"""Серверный rate limiter: N поисков за window секунд на пользователя.

Расходует квоту только после успешного поискового запроса.
Также даёт дебаунс для inline-кнопок (защита от спама нажатиями).
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class SearchRateLimiter:
    def __init__(self, limit: int = 3, window: int = 60) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    def set_window(self, limit: int, window: int) -> None:
        self.limit = limit
        self.window = window

    async def check(self, user_id: int) -> tuple[bool, int]:
        """Возвращает (разрешено, сколько секунд ждать)."""
        now = time.monotonic()
        async with self._lock:
            dq = self._hits[user_id]
            while dq and now - dq[0] >= self.window:
                dq.popleft()
            if len(dq) < self.limit:
                return True, 0
            wait = self.window - (now - dq[0])
            return False, max(1, int(wait) + 1)

    async def consume(self, user_id: int) -> None:
        now = time.monotonic()
        async with self._lock:
            dq = self._hits[user_id]
            dq.append(now)
            while dq and now - dq[0] >= self.window:
                dq.popleft()


class ButtonDebounce:
    """Игнорирует одинаковые нажатия кнопок чаще 0.8 сек на пользователя."""

    def __init__(self, gap: float = 0.8) -> None:
        self.gap = gap
        self._last: dict[tuple[int, str], float] = {}

    def ok(self, user_id: int, data: str) -> bool:
        key = (user_id, data)
        now = time.monotonic()
        last = self._last.get(key)
        if last is not None and now - last < self.gap:
            return False
        self._last[key] = now
        if len(self._last) > 2000:
            cutoff = now - 600
            for k, v in list(self._last.items()):
                if v < cutoff:
                    self._last.pop(k, None)
        return True