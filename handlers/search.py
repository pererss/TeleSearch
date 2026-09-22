"""Экран поиска: умный поиск по словам и поиск по фильтрам."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.search import FilterOptions
from core.states import cancel_keyboard
from core.texts import (
    CATEGORIES,
    LANGUAGES,
    SIZE_OPTIONS,
    TYPE_OPTIONS,
    lang_label_by_code,
    size_label_by_key,
    type_label_by_key,
)
from core.tgden import TgdenError
from handlers.common import svc

log = logging.getLogger(__name__)

# Фильтры по пользователям хранятся в памяти
_filters_state: dict[int, FilterOptions] = {}


def get_filters(uid: int) -> FilterOptions:
    if uid not in _filters_state:
        _filters_state[uid] = FilterOptions()
    return _filters_state[uid]


# ---------------------------------------------------------------- экраны

def search_screen_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Умный поиск по словам", callback_data="srch:smart")],
        [InlineKeyboardButton("⚙️ Поиск по фильтрам", callback_data="srch:filters")],
        [InlineKeyboardButton("« Назад", callback_data="menu:home")],
    ])


async def show_search_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = svc.db.texts["search_menu"]
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=search_screen_markup())
    except Exception:
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=search_screen_markup())


async def on_smart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid = update.effective_user.id
    svc.states.set(uid, "query")
    text = svc.db.texts["smart_search_prompt"]
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_keyboard())
    except Exception:
        await query.answer()


# ---------------------------------------------------------------- фильтры

def cat_label(f: FilterOptions) -> str:
    if not f.category:
        return "Любая"
    for slug, emoji, name in CATEGORIES:
        if slug == f.category:
            return f"{emoji} {name}"
    return f.category


def filter_screen_text(f: FilterOptions) -> str:
    return (
        svc.db.texts["filters_title"]
        + f"\n\nТип: **{type_label_by_key(f.type_key)}**"
        + f"\nКатегория: **{cat_label(f)}**"
        + f"\nЯзык: **{lang_label_by_code(f.language) if f.language else 'Любой'}**"
        + f"\nРазмер: **{size_label_by_key(f.size_key)}**"
    )


def filter_main_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Тип", callback_data="fl:t"),
         InlineKeyboardButton("Категория", callback_data="fl:c")],
        [InlineKeyboardButton("Язык", callback_data="fl:l"),
         InlineKeyboardButton("Размер", callback_data="fl:s")],
        [InlineKeyboardButton("🔎 Найти", callback_data="fl:go"),
         InlineKeyboardButton("🔄 Сбросить", callback_data="fl:reset")],
        [InlineKeyboardButton("« Назад", callback_data="menu:home")],
    ])


async def show_filters(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = True) -> None:
    query = update.callback_query
    if not from_callback:
        return
    f = get_filters(update.effective_user.id)
    text = filter_screen_text(f)
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=filter_main_markup())
    except Exception:
        await query.answer()


def build_choice_markup(options: list[tuple[str, ...]], prefix: str, none_value: str,
                        none_label: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(none_label, callback_data=f"{prefix}:{none_value}")]]
    row: list = []
    for opt in options:
        label = opt[1] if len(opt) > 1 else opt[0]
        value = opt[0]
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}:{value}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("« Назад", callback_data="fl:home")])
    return InlineKeyboardMarkup(rows)


async def show_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = []
    for key, label, _ in TYPE_OPTIONS:
        rows.append([InlineKeyboardButton(label, callback_data=f"fl:set:t:{key}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="fl:home")])
    await update.callback_query.edit_message_text("**Тип объектов**", parse_mode="Markdown",
                                                  reply_markup=InlineKeyboardMarkup(rows))


async def show_category_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = [[InlineKeyboardButton("Любая", callback_data="fl:set:c:none")]]
    row: list = []
    hidden = svc.db.settings.get("hidden_categories", [])
    for slug, emoji, name in CATEGORIES:
        if slug in hidden:
            continue
        row.append(InlineKeyboardButton(f"{emoji} {name}", callback_data=f"fl:set:c:{slug}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("« Назад", callback_data="fl:home")])
    await update.callback_query.edit_message_text("**Категория**", parse_mode="Markdown",
                                                  reply_markup=InlineKeyboardMarkup(rows))


async def show_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = [[InlineKeyboardButton("Любой", callback_data="fl:set:l:none")]]
    row: list = []
    for code, flag, name in LANGUAGES:
        row.append(InlineKeyboardButton(f"{flag} {name}", callback_data=f"fl:set:l:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("« Назад", callback_data="fl:home")])
    await update.callback_query.edit_message_text("**Язык**", parse_mode="Markdown",
                                                  reply_markup=InlineKeyboardMarkup(rows))


async def show_size_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = []
    for key, label, _, _ in SIZE_OPTIONS:
        rows.append([InlineKeyboardButton(label, callback_data=f"fl:set:s:{key}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="fl:home")])
    await update.callback_query.edit_message_text("**Размер аудитории**", parse_mode="Markdown",
                                                  reply_markup=InlineKeyboardMarkup(rows))


async def on_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    f = get_filters(uid)

    if data == "srch:filters":
        await show_filters(update, context)
        return
    if data == "fl:home":
        await show_filters(update, context)
        return
    if data == "fl:t":
        await show_type_choice(update, context)
        return
    if data == "fl:c":
        await show_category_choice(update, context)
        return
    if data == "fl:l":
        await show_lang_choice(update, context)
        return
    if data == "fl:s":
        await show_size_choice(update, context)
        return
    if data == "fl:reset":
        _filters_state[uid] = FilterOptions()
        await show_filters(update, context)
        return
    if data == "fl:go":
        await _run_filtered_search(update, context, f)
        return

    if data.startswith("fl:set:"):
        parts = data.split(":", 3)  # fl, set, <what>, <value>
        _, _, what, value = parts
        if what == "t":
            f.type_key = value
        elif what == "c":
            f.category = value if value != "none" else None
        elif what == "l":
            f.language = value if value != "none" else None
        elif what == "s":
            f.size_key = value
        await show_filters(update, context)
        return

    await query.answer()


# ---------------------------------------------------------------- поиск

async def _run_filtered_search(update: Update, context: ContextTypes.DEFAULT_TYPE, f: FilterOptions) -> None:
    query = update.callback_query
    uid = update.effective_user.id

    allowed, wait = await svc.limiter.check(uid)
    if not allowed:
        text = svc.db.texts["limit_msg"].replace("{seconds}", str(wait))
        try:
            await query.edit_message_text(text, parse_mode="Markdown")
        except Exception:
            await query.answer()
        return

    await query.edit_message_text("🔍 Ищу...")
    try:
        items = await svc.service.filtered(f)
    except TgdenError as exc:
        svc.stats.add_error(exc.kind, str(exc))
        await _fail(query, context, "", str(exc))
        return
    if not items:
        svc.states.clear(uid)
        await _empty(query, context)
        return
    await svc.limiter.consume(uid)
    svc.stats.add_search(
        categories=[f.category] if f.category else [],
        types=list({i.get("type") for i in items}),
    )
    await _show_results(update, context, header=svc.db.texts["results_header"], items=items)


async def _fail(query, context: ContextTypes.DEFAULT_TYPE, query_text: str, error: str) -> None:
    from core import notifications
    uid = query.from_user.id
    await notifications.search_error(context, uid, query_text, error, svc.states)
    try:
        await query.edit_message_text(svc.db.texts["search_error"], parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(svc.db.texts["search_error"], parse_mode="Markdown")


async def _empty(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await query.edit_message_text(svc.db.texts["no_results"], parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(svc.db.texts["no_results"], parse_mode="Markdown")


async def _show_results(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        header: str, items: list, extra: str = "") -> None:
    from handlers.results import render_first_page
    await render_first_page(update, context, header, items)


# ---- обработка текстового запроса умного поиска
async def on_text_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str) -> None:
    uid = update.effective_user.id
    query_text = " ".join(query_text.split())[:100]

    if not query_text or query_text.startswith("/"):
        await update.message.reply_text("Пожалуйста, введите текст запроса.")
        return

    allowed, wait = await svc.limiter.check(uid)
    if not allowed:
        text = svc.db.texts["limit_msg"].replace("{seconds}", str(wait))
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    await update.message.chat.send_action("typing")
    try:
        items = await svc.service.smart(query_text, "all")
    except TgdenError as exc:
        svc.stats.add_error(exc.kind, str(exc))
        await _fail_cmd(update, context, query_text, str(exc))
        return

    if not items:
        await update.message.reply_text(svc.db.texts["no_results"], parse_mode="Markdown")
        return

    await svc.limiter.consume(uid)
    svc.stats.add_search(query=query_text, types=list({i.get("type") for i in items}))
    header = f'{svc.db.texts["results_header"]}\n«{query_text}»'
    await _show_results(update, context, header, items)


async def _fail_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str, error: str) -> None:
    from core import notifications
    await notifications.search_error(context, update.effective_user.id, query_text, error, svc.states)
    try:
        await update.message.reply_text(svc.db.texts["search_error"], parse_mode="Markdown")
    except Exception:
        pass