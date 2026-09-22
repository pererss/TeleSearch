"""🎲 Случайное."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.formatting import esc, format_count, type_label
from core.tgden import TgdenError
from handlers.common import svc

log = logging.getLogger(__name__)


def _card(item: dict) -> tuple[str, InlineKeyboardMarkup]:
    title = esc(item.get("title", "—"))
    if item.get("link"):
        title = f'<a href="{esc(item["link"])}">{title}</a>'
    sub = esc(type_label(item))
    size = format_count(item.get("size"))
    if size:
        sub += f" · {size}"
    lines = [f"🎲 **Случайное**", "", title, sub]
    desc = item.get("description") or ""
    if desc:
        lines += ["", esc(desc[:220])]
    text = "\n".join(lines[:6])
    rows = [[InlineKeyboardButton("Открыть", url=item["link"])]] if item.get("link") else []
    rows.append([InlineKeyboardButton("🎲 Ещё", callback_data="rnd:go"),
                 InlineKeyboardButton("🏠 В меню", callback_data="menu:home")])
    return text, InlineKeyboardMarkup(rows)


async def run_random(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer()
    await query.message.chat.send_action("typing")
    try:
        item = await svc.service.random_item()
    except TgdenError as exc:
        svc.stats.add_error(exc.kind, str(exc))
        try:
            await query.edit_message_text(svc.db.texts["search_error"], parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(svc.db.texts["search_error"], parse_mode="Markdown")
        return
    if not item:
        try:
            await query.edit_message_text(svc.db.texts["no_results"], parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(svc.db.texts["no_results"], parse_mode="Markdown")
        return

    svc.stats.add_search(types=[item.get("type", "channel")])
    text, markup = _card(item)
    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        try:
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            log.exception("random card render")