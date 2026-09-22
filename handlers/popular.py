"""🔥 Популярное."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.tgden import TgdenError
from handlers.common import svc

log = logging.getLogger(__name__)


async def run_popular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.chat.send_action("typing")
    try:
        items = await svc.service.popular()
    except TgdenError as exc:
        svc.stats.add_error(exc.kind, str(exc))
        from core import notifications
        await notifications.search_error(context, update.effective_user.id, "popular", str(exc), svc.states)
        await query.message.reply_text(svc.db.texts["search_error"], parse_mode="Markdown")
        return
    if not items:
        await query.message.reply_text(svc.db.texts["no_results"], parse_mode="Markdown")
        return

    svc.stats.add_search(types=list({i.get("type") for i in items}))
    from handlers.results import render_first_page
    await render_first_page(update, context, svc.db.texts["popular_title"], items)