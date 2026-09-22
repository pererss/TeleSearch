"""Сервис поиска: умный поиск, фильтры, популярное, случайное, категории."""
from __future__ import annotations

import random
import secrets
import time

from .config import config
from .formatting import build_results_text
from .texts import CATEGORIES
from .tgden import TgdenClient, items_from

TYPE_LOOKUP: list[tuple[str, list[str]]] = [
    ("all", ["chat", "channel", "bot"]),
    ("chat", ["chat"]),
    ("channel", ["channel"]),
    ("bot", ["bot"]),
    ("chat+channel", ["chat", "channel"]),
    ("chat+bot", ["chat", "bot"]),
    ("channel+bot", ["channel", "bot"]),
]


def filter_types(key: str) -> list[str]:
    for k, types_ in TYPE_LOOKUP:
        if k == key:
            return types_
    return ["chat", "channel", "bot"]


SIZE_BUCKETS: list[tuple[str, int | None, int | None]] = [
    ("any", None, None),
    ("lt1k", None, 1000),
    ("1k10k", 1000, 10000),
    ("10k100k", 10000, 100000),
    ("gt100k", 100000, None),
]


def size_range(key: str) -> tuple[int | None, int | None]:
    for k, lo, hi in SIZE_BUCKETS:
        if k == key:
            return lo, hi
    return None, None


class FilterOptions:
    """Текущие фильтры пользователя."""

    def __init__(self) -> None:
        self.type_key = "all"
        self.category: str | None = None
        self.language: str | None = None
        self.size_key = "any"


def _filter_local(items: list[dict], language: str | None, size_key: str) -> list[dict]:
    lo, hi = size_range(size_key)
    out: list[dict] = []
    for it in items:
        if language and language not in it.get("language", []):
            continue
        size = it.get("size")
        if lo is not None and (size is None or size < lo):
            continue
        if hi is not None and (size is None or size >= hi):
            continue
        out.append(it)
    return out


def _merge_sorted(*lists_: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for lst in lists_:
        merged.extend(lst)
    merged.sort(key=lambda it: it.get("size") or 0, reverse=True)
    return merged


class ResultSession:
    """Хранит результаты поиска для пагинации и жалоб."""

    TTL = 1800

    def __init__(self, header: str, items: list[dict]) -> None:
        self.token = secrets.token_hex(4)
        self.header = header
        self.items = items
        self.created = time.monotonic()
        self.last_page = 0
        self.complained: set[int] = set()

    @property
    def total_pages(self) -> int:
        page_size = config.result_page_size or 5
        return max(1, (len(self.items) + page_size - 1) // page_size)


class ResultSessions:
    def __init__(self, max_size: int = 300) -> None:
        self._sessions: dict[str, ResultSession] = {}
        self._max = max_size

    def add(self, session: ResultSession) -> ResultSession:
        now = time.monotonic()
        for tok, s in list(self._sessions.items()):
            if now - s.created > s.TTL:
                self._sessions.pop(tok, None)
        if len(self._sessions) >= self._max:
            oldest = min(self._sessions.items(), key=lambda kv: kv[1].created)
            self._sessions.pop(oldest[0], None)
        self._sessions[session.token] = session
        return session

    def get(self, token: str) -> ResultSession | None:
        s = self._sessions.get(token)
        if s is None:
            return None
        if time.monotonic() - s.created > s.TTL:
            self._sessions.pop(token, None)
            return None
        return s

    def page_items(self, session: ResultSession, page: int) -> list[dict]:
        page_size = config.result_page_size or 5
        start = page * page_size
        return session.items[start:start + page_size]


class SearchService:
    def __init__(self, client: TgdenClient, sessions: ResultSessions) -> None:
        self.client = client
        self.sessions = sessions
        self.hidden_categories: list[str] = []

    # ---- умный поиск ----
    async def smart(self, query: str, type_key: str = "all") -> list[dict]:
        types_wanted = set(filter_types(type_key))
        pages = max(1, min(3, config.fetch_pages))
        merged: list[dict] = []
        for etype in types_wanted:
            for page in range(1, pages + 1):
                data = await self.client.search(query, type_=etype, page=page)
                merged.extend(await items_from(data))
        wanted = [it for it in merged if it.get("type") in types_wanted]
        wanted.sort(key=lambda it: it.get("size") or 0, reverse=True)
        return wanted[:200]

    # ---- поиск по фильтрам ----
    async def filtered(self, f: FilterOptions) -> list[dict]:
        types_wanted = filter_types(f.type_key)
        category = f.category
        language = f.language
        merge_parts: list[list[dict]] = []

        if "channel" in types_wanted:
            try:
                data = await self.client.channels(category=category)
                merge_parts.append(await items_from(data, "channel"))
            except Exception:
                pass
        if "chat" in types_wanted:
            try:
                data = await self.client.chats(category=category)
                merge_parts.append(await items_from(data, "chat"))
            except Exception:
                pass
        if "bot" in types_wanted and not category:
            try:
                data = await self.client.bots()
                merge_parts.append(await items_from(data, "bot"))
            except Exception:
                pass

        merged = _merge_sorted(*merge_parts) if merge_parts else []
        merged = _filter_local(merged, language, f.size_key)
        return merged[:200]

    # ---- популярное ----
    async def popular(self, limit: int = 50) -> list[dict]:
        data_ch = await self.client.channels()
        data_ct = await self.client.chats()
        data_b = await self.client.bots()
        merged = _merge_sorted(
            await items_from(data_ch, "channel"),
            await items_from(data_ct, "chat"),
            await items_from(data_b, "bot"),
        )
        return merged[:limit]

    # ---- случайное ----
    async def random_item(self) -> dict | None:
        cats = [c for c in CATEGORIES if c[0] not in self.hidden_categories]
        if not cats:
            cats = CATEGORIES
        for _ in range(5):
            slug, _emoji, _name = random.choice(cats)
            page = random.randint(1, 40)
            try:
                data = await self.client.channels(category=slug, page=page, use_cache=False)
                items = await items_from(data, "channel")
            except Exception:
                continue
            pool = [it for it in items if it.get("link")]
            if pool:
                return random.choice(pool)
        try:
            data = await self.client.channels(page=1)
            items = await items_from(data, "channel")
            pool = [it for it in items if it.get("link")]
            if pool:
                return random.choice(pool)
        except Exception:
            return None
        return None

    # ---- категории ----
    async def category(self, slug: str, limit: int = 100) -> list[dict]:
        data_ch = await self.client.channels(category=slug)
        data_ct = await self.client.chats(category=slug)
        merged = _merge_sorted(
            await items_from(data_ch, "channel"),
            await items_from(data_ct, "chat"),
        )
        return merged[:limit]

    # ---- рендеринг ----
    def build_session(self, header: str, items: list[dict]) -> ResultSession | None:
        if not items:
            return None
        return self.sessions.add(ResultSession(header, items))

    def render_page(self, session: ResultSession, page: int) -> tuple[str, list[dict]]:
        page = max(0, min(page, session.total_pages - 1))
        session.last_page = page
        items = self.sessions.page_items(session, page)
        header = session.header
        total = len(session.items)
        if total > len(items):
            header += f"\nНайдено: {total}"
        text = build_results_text(header, items[: config.result_page_size])
        return text, items