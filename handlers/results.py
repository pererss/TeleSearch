"""Рендеринг результатов, пагинация и жалобы."""
from __future__ import annotations

import html
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core import notifications
from core.config import config
from core.formatting import esc
from core.texts import COMPLAINT_REASONS
from handlers.common import svc

log = logging.getLogger(__name__)


def _reason_label(key: str) -> str:
    for k, label in COMPLAINT_REASONS:
        if k == key:
            return label
    return "Другое"


def _session_markup(session, page: int) -> InlineKeyboardMarkup:
    page_size = config.result_page_size
    start = page * page_size
    on_page = session.items[start:start + page_size]
    total_pages = session.total_pages

    rows: list[list[InlineKeyboardButton]] = []
    if on_page:
        rows.append([
            InlineKeyboardButton(f"⚠️{i + 1}", callback_data=f"cmp:pick:{session.token}:{start + i}")
            for i in range(len(on_page))
        ])
    nav = [InlineKeyboardButton("←", callback_data=f"res:nav:{session.token}:{page - 1}"),
           InlineKeyboardButton(f"{page + 1} / {total_pages}", callback_data=f"res:noop:{session.token}"),
           InlineKeyboardButton("→", callback_data=f"res:nav:{session.token}:{page + 1}")]
    rows.append(nav)
    rows.append([InlineKeyboardButton("🏠 В меню", callback_data="menu:home"),
                 InlineKeyboardButton("💬 Поддержка", callback_data="menu:support")])
    return InlineKeyboardMarkup(rows)


async def render_first_page(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            header: str, items: list) -> None:
    session = svc.service.build_session(header, items)
    if session is None:
        text = svc.db.texts["no_results"]
        if update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")
        return

    text, _items = svc.service.render_page(session, 0)
    markup = _session_markup(session, 0)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await update.callback_query.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def on_results_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data

    if data.startswith("res:noop:"):
        await query.answer()
        return

    if data.startswith("res:nav:"):
        _p, _n, token, page_str = data.split(":", 3)
        session = svc.service.sessions.get(token)
        if session is None:
            await query.answer("Данные устарели. Начни новый поиск.")
            await query.edit_message_text("Результаты устарели. Начни новый поиск.")
            return
        page = max(0, min(int(page_str or 0), session.total_pages - 1))
        text, _items = svc.service.render_page(session, page)
        try:
            await query.edit_message_text(text, parse_mode="HTML",
                                          reply_markup=_session_markup(session, page))
        except Exception:
            await query.answer()
        return

    await query.answer()


async def on_complaint_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id

    if data.startswith("cmp:pick:"):
        _c, _p, token, idx_str = data.split(":", 3)
        session = svc.service.sessions.get(token)
        if session is None:
            await query.answer("Данные устарели.")
            return
        idx = int(idx_str or 0)
        item = session.items[idx] if 0 <= idx < len(session.items) else None
        if item is None:
            await query.answer()
            return
        title = esc(item.get("title", "—"))
        rows = []
        for key, label in COMPLAINT_REASONS:
            rows.append([InlineKeyboardButton(label, callback_data=f"cmp:send:{token}:{idx}:{key}")])
        rows.append([InlineKeyboardButton("« Назад к результатам", callback_data=f"cmp:back:{token}:{idx}")])
        text = (f"⚠️ **Жалоба**\n\nОбъект:\n{title}\n\nУкажи причину:")
        try:
            await query.edit_message_text(text, parse_mode="HTML",
                                          reply_markup=InlineKeyboardMarkup(rows))
        except Exception:
            await query.answer()
        return

    if data.startswith("cmp:back:"):
        _c, _b, token, _idx = data.split(":", 3)
        session = svc.service.sessions.get(token)
        if session is None:
            await query.answer("Данные устарели.")
            return
        page = session.last_page
        text, _items = svc.service.render_page(session, page)
        try:
            await query.edit_message_text(text, parse_mode="HTML",
                                          reply_markup=_session_markup(session, page))
        except Exception:
            await query.answer()
        return

    if data.startswith("cmp:send:"):
        _c, _s, token, idx_str, reason = data.split(":", 4)
        session = svc.service.sessions.get(token)
        if session is None:
            await query.answer("Данные устарели.")
            return
        idx = int(idx_str or 0)
        if idx in session.complained:
            await query.answer("Вы уже отправляли жалобу на этот объект.")
            return
        session.complained.add(idx)
        item = session.items[idx] if 0 <= idx < len(session.items) else {}
        svc.stats.add_complaint()
        complaint = {
            "id": len(svc.db.complaints) + 1,
            "user_id": uid,
            "username": update.effective_user.username or "",
            "item_title": item.get("title", "—"),
            "item_link": item.get("link", ""),
            "reason": _reason_label(reason),
            "ts": int(time.time()),
            "status": "open",
        }
        svc.db.complaints.append(complaint)
        await svc.db.save_all()
        await notifications.new_complaint(context, uid, complaint["item_title"],
                                          complaint["item_link"], complaint["reason"])
        await query.answer(svc.db.texts["complaint_sent"], show_alert=True)
        page = session.last_page
        text, _items = svc.service.render_page(session, page)
        try:
            await query.edit_message_text(text, parse_mode="HTML",
                                          reply_markup=_session_markup(session, page))
        except Exception:
            pass
        return

    await query.answer()