"""Точка входа: сборка приложения, маршрутизация, запуск бота."""
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core import notifications
from core.config import config
from core.ratelimit import ButtonDebounce, SearchRateLimiter
from core.search import ResultSessions, SearchService
from core.states import CANCEL, States
from core.stats import Stats
from core.storage import Store
from core.texts import SETTINGS_DEFAULTS, TEXTS_DEFAULTS
from core.tgden import TgdenClient
from handlers import admin, categories, menu, popular, random_item, results, search, support
from handlers.common import is_blocked, main_menu_markup, svc

log = logging.getLogger(__name__)


def setup_logging() -> None:
    handlers_: list[logging.Handler] = [logging.StreamHandler()]
    if config.log_to_file:
        config.data_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(config.data_dir / "bot.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handlers_.append(fh)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers_,
    )


# ---------------------------------------------------------------- services

async def wire_services() -> None:
    """Заполняет svc в текущем event loop (важно: JSON-хранилище асинхронное)."""
    svc.db = Store(config.data_dir, TEXTS_DEFAULTS, SETTINGS_DEFAULTS)
    await svc.db.load_all()
    svc.stats = Stats(svc.db)
    svc.states = States()
    svc.limiter = SearchRateLimiter(
        svc.db.settings.get("search_limit", 3),
        svc.db.settings.get("search_window", 60))
    svc.debounce = ButtonDebounce()
    svc.client = TgdenClient()
    svc.service = SearchService(svc.client, ResultSessions())
    svc.service.hidden_categories = svc.db.settings.get("hidden_categories", [])
    svc.broadcast_pending = None
    admin._apply_settings()


# ---------------------------------------------------------------- routing

async def _on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    uid = update.effective_user.id

    if not svc.debounce.ok(uid, data):
        try:
            await query.answer()
        except Exception:
            pass
        return

    try:
        if data == CANCEL:
            await menu.on_cancel(update, context)
            return

        prefix = data.split(":", 1)[0]

        if prefix == "menu":
            await menu.on_menu_callback(update, context)
        elif prefix == "cat":
            parts = data.split(":", 2)
            if len(parts) == 3 and parts[1] == "show":
                await categories.on_category_show(update, context, parts[2])
            else:
                await query.answer()
        elif prefix in ("srch", "fl"):
            if data == "srch:smart":
                await search.on_smart(update, context)
            else:
                await search.on_filter_callback(update, context)
        elif prefix == "pop":
            await popular.run_popular(update, context)
        elif prefix == "rnd":
            await random_item.run_random(update, context)
        elif prefix == "res":
            await results.on_results_callback(update, context)
        elif prefix == "cmp":
            await results.on_complaint_callback(update, context)
        elif prefix == "adm":
            await admin.on_admin_callback(update, context)
        else:
            await query.answer()
    except Exception:
        log.exception("callback %r failed", data)
        try:
            await query.answer()
        except Exception:
            pass


async def _on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_chat.type != "private":
        return
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    uid = user.id
    svc.stats.register_user(uid, user.first_name or "", user.username or "")
    if is_blocked(uid):
        await update.message.reply_text(svc.db.texts["blocked_msg"])
        return

    text = update.message.text.strip()
    if not text:
        return

    state = svc.states.get(uid)
    if state:
        mode = state[0]
        if mode.startswith("admin"):
            await admin.on_admin_text(update, context, text)
        elif mode == "query":
            await search.on_text_query(update, context, text)
        elif mode == "support_msg":
            await support.on_support_message(update, context, text)
        else:
            svc.states.clear(uid)
    else:
        await update.message.reply_text(
            "Воспользуйся кнопками меню 👇", reply_markup=main_menu_markup())


async def _on_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        svc.stats.add_error("internal", repr(context.error))
    except Exception:
        pass
    log.error("Unhandled error", exc_info=context.error)


# ---------------------------------------------------------------- background

async def _monitor(app: Application) -> None:
    await asyncio.sleep(5)
    while True:
        try:
            recent = svc.stats.errors_recent(300)
            if len(recent) >= 3:
                await notifications.system_many_errors(SimpleNamespace(bot=app.bot),
                                                       len(recent))
            await svc.db.save_all()
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("monitor")
        await asyncio.sleep(60)


async def _post_init(app: Application) -> None:
    await wire_services()
    app.bot_data["monitor"] = asyncio.create_task(_monitor(app))


async def _post_shutdown(app: Application) -> None:
    task = app.bot_data.get("monitor")
    if task:
        task.cancel()
    try:
        await svc.db.save_all()
    except Exception:
        pass
    try:
        await svc.client.close()
    except Exception:
        pass


def build_app() -> Application:
    app = Application.builder() \
        .token(config.bot_token) \
        .concurrent_updates(True) \
        .post_init(_post_init) \
        .post_shutdown(_post_shutdown) \
        .build()

    app.add_handler(CommandHandler("start", menu.cmd_start))
    app.add_handler(CommandHandler("admin", menu.cmd_admin))
    app.add_handler(CallbackQueryHandler(_on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_text))
    app.add_error_handler(_on_error)
    return app


def main() -> None:
    setup_logging()
    if not config.token_ok:
        log.error("BOT_TOKEN не задан (или невалиден) — создай .env по .env.example")
        return
    app = build_app()
    log.info("TeleSearch bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()