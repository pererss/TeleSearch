"""Уведомления администратору. Кратко, только о важном."""
from __future__ import annotations

import logging
import time
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .config import config
from .states import States

log = logging.getLogger(__name__)

_dedupe: dict[str, float] = {}


def _dedup(key: str, seconds: float = 60) -> bool:
    now = time.monotonic()
    last = _dedupe.get(key)
    if last is not None and now - last < seconds:
        return False
    _dedupe[key] = now
    if len(_dedupe) > 200:
        for k in list(_dedupe.keys()):
            if now - _dedupe[k] > 3600:
                _dedupe.pop(k, None)
    return True


async def notify(context: ContextTypes.DEFAULT_TYPE, text: str, buttons: Any = None) -> bool:
    """Отправляет сообщение администратору. Никогда не роняет хэндлер."""
    try:
        await context.bot.send_message(config.admin_id, text, parse_mode="HTML", reply_markup=buttons)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Не удалось уведомить админа: %s", exc)
        return False


def reply_button(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💬 Ответить", callback_data=f"adm:sup:reply:{ticket_id}")
    ]])


async def new_user(context: ContextTypes.DEFAULT_TYPE, user_id: int, total: int) -> None:
    await notify(context, f"👤 Новый пользователь\nID: {user_id}\nВсего: {total}")


async def new_ticket(context: ContextTypes.DEFAULT_TYPE, ticket_id: int, user_id: int,
                     text: str) -> None:
    snippet = text.strip().replace("\n", " ")[:180]
    await notify(context,
                 f"📨 Новая поддержка\nID: {user_id}\nТекст: {snippet}",
                 reply_button(ticket_id))


async def new_complaint(context: ContextTypes.DEFAULT_TYPE, reporter_id: int,
                        item_title: str, item_link: str, reason: str) -> None:
    link = item_title
    if item_link:
        link = f'<a href="{item_link}">{item_title}</a>'
    await notify(context,
                 f"🚨 Жалоба\nПользователь: {reporter_id}\n"
                 f"Объект: {link}\nПричина: {reason}")


async def search_error(context: ContextTypes.DEFAULT_TYPE, user_id: int, query: str,
                       error: str, states: States) -> None:
    # Не спамить: не больше 1 уведомления об однотипной ошибке в минуту
    if not _dedup(type(error).__name__, 60):
        return
    snippet = str(error).replace("\n", " ")[:160]
    await notify(context,
                 f"❌ Ошибка поиска\nПользователь: {user_id}\n"
                 f"Запрос: {query or '—'}\nОшибка: {snippet}")


async def system_many_errors(context: ContextTypes.DEFAULT_TYPE, count: int) -> None:
    if not _dedup("sys:api", 300):
        return
    await notify(context,
                 f"⚠️ TGDen API недоступен\nОшибок за последние 5 минут: {count}")


async def reply_delivered(context: ContextTypes.DEFAULT_TYPE, user_id: int, ticket_id: int) -> None:
    await notify(context, f"✅ Ответ отправлен пользователю {user_id} (тикет #{ticket_id})")


async def reply_failed(context: ContextTypes.DEFAULT_TYPE, user_id: int, ticket_id: int) -> None:
    await notify(context, f"⚠️ Не удалось доставить ответ пользователю {user_id} (тикет #{ticket_id})")


async def broadcast_done(context: ContextTypes.DEFAULT_TYPE, ok: int, failed: int) -> None:
    await notify(context, f"📢 Рассылка завершена ✅\nДоставлено: {ok}\nНе доставлено: {failed}")