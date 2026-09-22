"""Сбор статистики: пользователи, поиски, категории, типы, ошибки."""
from __future__ import annotations

import time
from collections import deque
from datetime import date, timedelta

from .storage import Store


def _day(dt: date | None = None) -> str:
    return (dt or date.today()).isoformat()


class Stats:
    def __init__(self, db: Store) -> None:
        self.db = db
        self._err_ring: deque[dict] = deque(maxlen=200)

    # ---- пользователи ----
    def register_user(self, user_id: int, first_name: str = "", username: str = "") -> bool:
        """Возвращает True, если пользователь новый."""
        rec = self.db.users.get(str(user_id))
        now = round(time.time())
        if rec is None:
            self.db.users[str(user_id)] = {
                "first_seen": now,
                "last_seen": now,
                "name": first_name,
                "username": username,
                "blocked": False,
            }
            self._add_by_date(_day(), "new_users", 1)
            return True
        rec["last_seen"] = now
        if username:
            rec["username"] = username
        if first_name:
            rec["name"] = first_name
        return False

    def _add_by_date(self, day: str, field: str, n: int = 1) -> None:
        by_date = self.db.stats.setdefault("by_date", {})
        entry = by_date.setdefault(day, {"searches": 0, "new_users": 0})
        entry[field] = entry.get(field, 0) + n

    # ---- поиски ----
    def add_search(self, query: str = "", categories: list[str] | None = None,
                   types: list[str] | None = None) -> None:
        stats = self.db.stats
        query = (query or "").strip()
        if query:
            stats.setdefault("queries", {})[query] = stats["queries"].get(query, 0) + 1
        for cat in categories or []:
            stats.setdefault("categories", {})[cat] = stats["categories"].get(cat, 0) + 1
        for t in types or []:
            stats.setdefault("types", {})[t] = stats["types"].get(t, 0) + 1
        self._add_by_date(_day(), "searches", 1)

    def add_result_types(self, types: list[str]) -> None:
        stats = self.db.stats
        for t in types:
            stats.setdefault("types", {})[t] = stats["types"].get(t, 0) + 1

    # ---- тикеты и жалобы ----
    def add_ticket(self) -> None:
        self.db.stats["tickets_open"] += 1
        self.db.stats["tickets_total"] += 1

    def close_ticket(self) -> None:
        if self.db.stats["tickets_open"] > 0:
            self.db.stats["tickets_open"] -= 1

    def add_complaint(self) -> None:
        self.db.stats["complaints_open"] += 1
        self.db.stats["complaints_total"] += 1

    def close_complaint(self) -> None:
        if self.db.stats["complaints_open"] > 0:
            self.db.stats["complaints_open"] -= 1

    # ---- ошибки ----
    def add_error(self, kind: str, detail: str) -> None:
        rec = {"ts": time.time(), "kind": kind, "detail": str(detail)[:300]}
        self._err_ring.append(rec)
        self.db.stats.setdefault("errors", []).append(rec)
        errors = self.db.stats["errors"]
        if len(errors) > self._err_ring.maxlen:
            self.db.stats["errors"] = errors[-self._err_ring.maxlen:]
        self.db.stats["errors_total"] = self.db.stats.get("errors_total", 0) + 1

    def errors_recent(self, seconds: int = 300) -> list[dict]:
        now = time.time()
        return [e for e in self._err_ring if now - e["ts"] <= seconds]

    # ---- сводки ----
    def summary(self) -> dict:
        db = self.db
        total = len(db.users)
        blocked = sum(1 for u in db.users.values() if u.get("blocked"))
        today = _day()
        week_start = (date.today() - timedelta(days=6)).isoformat()
        day_s = db.stats["by_date"].get(today, {})
        week_new = 0
        week_searches = 0
        for k, v in db.stats["by_date"].items():
            if k >= week_start:
                week_new += v.get("new_users", 0)
                week_searches += v.get("searches", 0)
        errors_today = sum(1 for e in db.stats["errors"] if e["ts"] >= time.time() - 86400)
        return {
            "total": total,
            "blocked": blocked,
            "new_today": day_s.get("new_users", 0),
            "new_week": week_new,
            "searches_today": day_s.get("searches", 0),
            "searches_week": week_searches,
            "tickets_open": db.stats["tickets_open"],
            "tickets_total": db.stats["tickets_total"],
            "complaints_open": db.stats["complaints_open"],
            "complaints_total": db.stats["complaints_total"],
            "errors_today": errors_today,
            "errors_total": db.stats["errors_total"],
        }

    def top(self, key: str, n: int = 10):
        data = self.db.stats.get(key, {})
        return sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def types(self) -> dict:
        return self.db.stats.get("types", {})