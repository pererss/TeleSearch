"""Общие помощники и глобальное состояние бота."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.config import config

log = logging.getLogger(__name__)


class BotServices:
    """Собранные зависимости бота (заполняются в bot.py)."""

    def __init__(self) -> None:
        self.db = None            # Store
        self.stats = None         # Stats
        self.states = None        # States
        self.limiter = None       # SearchRateLimiter
        self.debounce = None      # ButtonDebounce
        self.client = None        # TgdenClient
        self.service = None       # SearchService


svc = BotServices()


def is_admin(user_id: int) -> bool:
    return user_id == config.admin_id


def is_blocked(user_id: int) -> bool:
    if svc.db is None:
        return False
    return bool(svc.db.users.get(str(user_id), {}).get("blocked"))


def blk(name: str = "") -> str:
    return name[:120]


def main_menu_markup() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🔎 Поиск групп, каналов и ботов", callback_data="menu:search")],
        [InlineKeyboardButton("🔥 Популярное", callback_data="menu:popular"),
         InlineKeyboardButton("🗂️ Категории", callback_data="menu:categories")],
        [InlineKeyboardButton("🎲 Случайное", callback_data="menu:random"),
         InlineKeyboardButton("💬 Поддержка", callback_data="menu:support")],
    ]
    return InlineKeyboardMarkup(rows)


def admin_markup_note(user_id: int) -> InlineKeyboardMarkup | None:
    if is_admin(user_id):
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("⚙️ Админка", callback_data="menu:admin")
        ]])
    return None


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = True) -> None:
    text = svc.db.texts["main_menu"] if svc.db else "🔎 Найди нужную группу, канал или бота в Telegram."
    text = f"{text}\n\nВыбери раздел:"

    markup = main_menu_markup()
    admin_btn = admin_markup_note(update.effective_user.id)
    if admin_btn:
        markup.inline_keyboard += admin_btn.inline_keyboard

    if edit and update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    elif update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


def answer_toast(query, text: str) -> None:
    """Обёртка для короткого toast-ответа на колбэк."""
    import asyncio
    asyncio.ensure_future(_toast(query, text))


async def _toast(query, text: str) -> None:
    try:
        await query.answer(text, show_alert=False)
    except Exception:
        pass