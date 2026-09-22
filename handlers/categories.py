"""Категории: список тем и переход к результатам по категории."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.texts import CATEGORIES
from core.tgden import TgdenError
from handlers.common import svc

log = logging.getLogger(__name__)


def _visible() -> list[tuple[str, str, str]]:
    hidden = svc.db.settings.get("hidden_categories", []) if svc.db else []
    return [c for c in CATEGORIES if c[0] not in hidden]


def categories_markup() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list = []
    for slug, emoji, name in _visible():
        row.append(InlineKeyboardButton(f"{emoji} {name}", callback_data=f"cat:show:{slug}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("« Назад", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = svc.db.texts["categories_title"]
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=categories_markup())
    except Exception:
        await query.answer()


async def on_category_show(update: Update, context: ContextTypes.DEFAULT_TYPE, slug: str) -> None:
    query = update.callback_query
    meta = next((c for c in CATEGORIES if c[0] == slug), None)
    await query.answer()
    if meta is None:
        return
    _emoji, name = meta[1], meta[2]

    header = f"🗂️ **{name}**"
    try:
        items = await svc.service.category(slug)
    except TgdenError as exc:
        svc.stats.add_error(exc.kind, str(exc))
        await query.message.reply_text(svc.db.texts["search_error"], parse_mode="Markdown")
        return
    if not items:
        await query.message.reply_text(svc.db.texts["no_results"], parse_mode="Markdown")
        return

    svc.stats.add_search(categories=[slug], types=list({i.get("type") for i in items}))
    from handlers.results import render_first_page
    await render_first_page(update, context, header, items)