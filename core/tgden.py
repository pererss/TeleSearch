"""Клиент публичного каталога TGDen (бесплатный API) с TTL-кэшем.

Использует открытые эндпоинты:
  GET /api/v1/search?q=...&type=all|chat|channel|bot&page=N
  GET /api/v1/channels?category=...&language=...&page=N
  GET /api/v1/chats?category=...&page=N
  GET /api/v1/bots?page=N
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .config import config

log = logging.getLogger(__name__)

USER_AGENT = "TeleSearchBot/0.1 (+https://t.me/TeleSearch_bot)"
API_PATH = "/api/v1"

# TTL кэша, сек (по типам запросов)
TTL_SEARCH = 120
TTL_LISTING = 600

RESULT_PAGE = 24  # сколько приходит за один запрос к каталогу


class TgdenError(Exception):
    """Ошибка внешнего каталога с человекочитаемой причиной."""

    def __init__(self, message: str, kind: str = "api") -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


class _Cache(dict):
    """Ключ -> (expires, value)."""

    def get_fresh(self, key: str):
        item = self.get(key)
        if not item:
            return None
        expires, value = item
        if time.monotonic() > expires:
            self.pop(key, None)
            return None
        return value

    def put(self, key: str, value: Any, ttl: float) -> None:
        if len(self) > 400:
            now = time.monotonic()
            for k, v in list(self.items()):
                if now > v[0]:
                    self.pop(k, None)
        self[key] = (time.monotonic() + ttl, value)


def _norm_type(raw: str | None) -> str:
    return (raw or "").strip().lower()


def normalize_item(raw: dict, forced_type: str | None = None) -> dict:
    """Приводит элемент каталога к единому виду для бота."""
    etype = forced_type or _norm_type(raw.get("entity_type"))
    if not etype:
        if "subscribers_count" in raw or "avg_post_reach" in raw:
            etype = "channel"
        elif "members_count" in raw:
            etype = "chat"
        else:
            etype = "bot"

    size = raw.get("subscribers_count")
    if size is None:
        size = raw.get("members_count")
    if size is None:
        size = raw.get("members")
    try:
        size = int(size) if size is not None else None
    except (TypeError, ValueError):
        size = None

    username = raw.get("username") or ""
    link = None
    if username:
        link = f"https://t.me/{username}"
    else:
        invite = raw.get("invite_hash")
        if invite and not raw.get("is_private"):
            link = f"https://t.me/+{invite}"

    lang = raw.get("language") or raw.get("languages") or []
    if not isinstance(lang, list):
        lang = [str(lang)] if lang else []

    cats = raw.get("categories") or []
    if not isinstance(cats, list):
        cats = [str(cats)] if cats else []

    title = raw.get("title") or raw.get("first_name") or "—"
    return {
        "type": etype,
        "title": title,
        "username": username,
        "description": raw.get("description") or raw.get("description_ai_summary") or "",
        "size": size,
        "language": [str(x) for x in lang],
        "categories": [str(x) for x in cats],
        "link": link,
        "verified": bool(raw.get("verified")),
    }


def _cache_key(endpoint: str, params: dict) -> str:
    items = sorted((k, str(v)) for k, v in params.items() if v not in (None, "", []))
    return endpoint + "?" + repr(items)


class TgdenClient:
    def __init__(self) -> None:
        self.base = config.tgden_base
        self._cache = _Cache()
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base,
                timeout=httpx.Timeout(15.0, connect=10.0),
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, endpoint: str, params: dict, cache_ok: bool, ttl: float) -> dict:
        params = {k: v for k, v in params.items() if v not in (None, "", [])}
        key = _cache_key(endpoint, params)
        cached = self._cache.get_fresh(key)
        if cache_ok and cached is not None:
            return cached

        client = await self._get_client()
        try:
            resp = await client.get(API_PATH + endpoint, params=params)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise TgdenError(f"TGDen timeout: {type(exc).__name__}", kind="timeout") from exc
        except httpx.HTTPError as exc:
            raise TgdenError(f"TGDen network: {type(exc).__name__}", kind="network") from exc

        if resp.status_code != 200:
            raise TgdenError(f"TGDen HTTP {resp.status_code}", kind=f"http_{resp.status_code}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise TgdenError("TGDen bad payload", kind="parse") from exc

        if not isinstance(data, dict):
            raise TgdenError("TGDen bad payload", kind="parse")

        if cache_ok:
            self._cache.put(key, data, ttl)
        return data

    async def search(self, query: str, type_: str = "all", page: int = 1, use_cache: bool = True) -> dict:
        return await self._request(
            "/search",
            {"q": query, "type": type_, "page": page},
            cache_ok=use_cache,
            ttl=TTL_SEARCH,
        )

    async def channels(self, category: str | None = None, language: str | None = None,
                       page: int = 1, use_cache: bool = True) -> dict:
        return await self._request(
            "/channels",
            {"category": category, "language": language, "page": page},
            cache_ok=use_cache,
            ttl=TTL_LISTING,
        )

    async def chats(self, category: str | None = None, language: str | None = None,
                    page: int = 1, use_cache: bool = True) -> dict:
        return await self._request(
            "/chats",
            {"category": category, "language": language, "page": page},
            cache_ok=use_cache,
            ttl=TTL_LISTING,
        )

    async def bots(self, page: int = 1, use_cache: bool = True) -> dict:
        return await self._request("/bots", {"page": page}, cache_ok=use_cache, ttl=TTL_LISTING)


async def items_from(data: dict, forced_type: str | None = None) -> list[dict]:
    """Извлекает и нормализует элементы ответа."""
    raw_items = data.get("items") or []
    out = []
    for raw in raw_items:
        item = normalize_item(raw, forced_type)
        if item["link"]:
            out.append(item)
    return out