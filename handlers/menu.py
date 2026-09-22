"""Главное меню и навигация."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core import notifications
from handlers.common import is_admin, is_blocked, show_main_menu, svc

log = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat and update.effective_chat.type != "private":
        return
    user = update.effective_user
    uid = user.id
    new_user = svc.stats.register_user(uid, user.first_name or "", user.username or "")
    if new_user and svc.db.settings.get("notify_new_user", True):
        await notifications.new_user(context, uid, len(svc.db.users))

    if is_blocked(uid):
        await update.message.reply_text("⛔ Доступ ограничен.")
        return

    svc.states.clear(uid)
    await show_main_menu(update, context, edit=False)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from handlers.admin import show_admin_panel
    if update.effective_chat and update.effective_chat.type != "private":
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    svc.states.clear(update.effective_user.id)
    await show_admin_panel(update, context)


async def on_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    svc.states.clear(uid)

    if data == "menu:home":
        await show_main_menu(update, context, edit=True)
        return

    if data == "menu:search":
        from handlers.search import show_search_screen
        await show_search_screen(update, context)
        return

    if data == "menu:popular":
        from handlers.popular import run_popular
        await run_popular(update, context)
        return

    if data == "menu:categories":
        from handlers.categories import show_categories
        await show_categories(update, context)
        return

    if data == "menu:random":
        from handlers.random_item import run_random
        await run_random(update, context)
        return

    if data == "menu:support":
        from handlers.support import show_support
        await show_support(update, context)
        return

    if data == "menu:admin":
        from handlers.admin import show_admin_panel
        if is_admin(uid):
            await show_admin_panel(update, context)
        else:
            await query.answer("⛔ Доступ запрещён.")
        return

    await query.answer()


async def on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    svc.states.clear(update.effective_user.id)
    try:
        await query.edit_message_text("Отменено.")
    except Exception:
        await query.answer()
    await show_main_menu(update, context, edit=False)