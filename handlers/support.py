"""💬 Поддержка: сообщение пользователя -> администратору."""
from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from core import notifications
from core.states import cancel_keyboard
from handlers.common import svc

log = logging.getLogger(__name__)


async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid = update.effective_user.id
    svc.states.set(uid, "support_msg")
    text = svc.db.texts["support_prompt"]
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_keyboard())
    except Exception:
        await query.answer()


async def on_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    uid = update.effective_user.id
    svc.states.clear(uid)
    text = text.strip()[:2000]
    if not text:
        await update.message.reply_text("Сообщение пустое. Напиши, что тебе нужно.")
        return

    ticket_id = len(svc.db.tickets) + 1
    svc.db.tickets.append({
        "id": ticket_id,
        "user_id": uid,
        "username": update.effective_user.username or "",
        "text": text,
        "ts": int(time.time()),
        "status": "open",
        "replies": [],
    })
    svc.stats.add_ticket()
    await svc.db.save_all()
    await notifications.new_ticket(context, ticket_id, uid, text)
    await update.message.reply_text(svc.db.texts["support_sent"], parse_mode="Markdown")