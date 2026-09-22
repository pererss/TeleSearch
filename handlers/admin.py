"""⚙️ Админ-панель (только для ADMIN_ID)."""
from __future__ import annotations

import asyncio
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.texts import CATEGORIES, SETTINGS_DEFAULTS, TEXTS_DEFAULTS
from handlers.common import is_admin, svc

log = logging.getLogger(__name__)

LOG_RING: list[str] = []


def log_line(text: str) -> None:
    LOG_RING.append(f"[{time.strftime('%H:%M:%S')}] {text}")
    if len(LOG_RING) > 300:
        del LOG_RING[:-300]


def _admin() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("👤 Пользователи", callback_data="adm:users"),
         InlineKeyboardButton("📊 Статистика", callback_data="adm:stats")],
        [InlineKeyboardButton("🔎 Статистика поиска", callback_data="adm:sstats")],
        [InlineKeyboardButton("📨 Поддержка", callback_data="adm:support"),
         InlineKeyboardButton("🚨 Жалобы", callback_data="adm:complaints")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="adm:bcast"),
         InlineKeyboardButton("📝 Тексты", callback_data="adm:texts")],
        [InlineKeyboardButton("🗂️ Категории", callback_data="adm:cats"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="adm:settings")],
        [InlineKeyboardButton("📋 Логи", callback_data="adm:logs"),
         InlineKeyboardButton("🚫 Блокировки", callback_data="adm:blocklist")],
        [InlineKeyboardButton("« В меню", callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(rows)


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "⚙️ **Админ-панель**\nВыбери раздел:", parse_mode="Markdown", reply_markup=_admin())
    elif update.message:
        await update.message.reply_text(
            "⚙️ **Админ-панель**\nВыбери раздел:", parse_mode="Markdown", reply_markup=_admin())


def find_user(token: str):
    t = token.strip().lstrip("@").lower()
    if not t:
        return None, None
    for key, rec in svc.db.users.items():
        if key == t or (rec.get("username") or "").lower() == t:
            return int(key), rec
    if t.isdigit():
        return int(t), None
    return None, None


def _user_line(uid: int, rec: dict | None) -> str:
    if rec is None:
        return f"Пользователь {uid}: не найден."
    state = "🚫 заблокирован" if rec.get("blocked") else "✅ активен"
    name = rec.get("name") or "—"
    uname = f"@{rec.get('username')}" if rec.get("username") else "—"
    return (
        f"🆔 ID: {uid}\n"
        f"👤 Имя: {name}\n"
        f"📛 @{rec.get('username') or ''}\n"
        f"Ссылка: {uname}\n"
        f"Первый визит: {time.strftime('%d.%m %H:%M', time.localtime(rec.get('first_seen', 0)))}\n"
        f"Последняя активность: {time.strftime('%d.%m %H:%M', time.localtime(rec.get('last_seen', 0)))}\n"
        f"Статус: {state}"
    )


def _back_to(section: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("« Назад", callback_data=f"adm:{section}")
    ]])


# ---------------------------------------------------------------- секции

async def adm_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    s = svc.stats.summary()
    text = (
        f"👤 **Пользователи**\n\n"
        f"Всего: {s['total']}\n"
        f"Новых сегодня: {s['new_today']}\n"
        f"Заблокировано: {s['blocked']}"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Найти пользователя", callback_data="adm:usr:find")],
        [InlineKeyboardButton("🚫 Заблокировать", callback_data="adm:usr:block")],
        [InlineKeyboardButton("🔓 Разблокировать", callback_data="adm:usr:unblock")],
        [InlineKeyboardButton("« Назад", callback_data="adm:home")],
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    s = svc.stats.summary()
    text = (
        f"📊 **Статистика**\n\n"
        f"Всего пользователей: {s['total']}\n"
        f"Новых сегодня: {s['new_today']}\n"
        f"Новых за неделю: {s['new_week']}\n"
        f"Поиски сегодня: {s['searches_today']}\n"
        f"Поиски за неделю: {s['searches_week']}\n"
        f"Жалоб: {s['complaints_total']} (открыто {s['complaints_open']})\n"
        f"Обращений: {s['tickets_total']} (открыто {s['tickets_open']})\n"
        f"Ошибок сегодня: {s['errors_today']}"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_back_to("home"))


async def adm_search_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    types_map = {"chat": "👥 Группы", "channel": "📢 Каналы", "bot": "🤖 Боты"}
    types = svc.stats.types()
    types_line = "\n".join(f"{types_map.get(k, k)}: {v}" for k, v in types.items())
    top_q = svc.stats.top("queries", 8)
    q_line = "\n".join(f"{q}: {n}" for q, n in top_q) or "—"
    top_c = svc.stats.top("categories", 8)
    c_line = "\n".join(f"{c}: {n}" for c, n in top_c) or "—"
    text = (
        f"🔎 **Статистика поиска**\n\n"
        f"**Типы:**\n{types_line}\n\n"
        f"**Популярные запросы:**\n{q_line}\n\n"
        f"**Популярные категории:**\n{c_line}"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_back_to("home"))


async def adm_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tickets = [t for t in svc.db.tickets if t.get("status") == "open"] + \
              [t for t in svc.db.tickets if t.get("status") == "closed"]
    tickets = tickets[-10:]
    if not tickets:
        await query.edit_message_text("📨 Обращений пока нет.", reply_markup=_back_to("home"))
        return
    rows = []
    for t in tickets:
        mark = "🟢" if t["status"] == "open" else "⚪"
        label = f"{mark} #{t['id']} · {t.get('user_id')} · {t['text'][:24]}"
        rows.append([InlineKeyboardButton(label, callback_data=f"adm:sup:open:{t['id']}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="adm:home")])
    await query.edit_message_text("📨 **Поддержка** (последние):", parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(rows))


async def adm_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    items = list(reversed(svc.db.complaints[-10:]))
    if not items:
        await query.edit_message_text("🚨 Жалоб пока нет.", reply_markup=_back_to("home"))
        return
    rows = []
    for c in items:
        mark = "🟢" if c["status"] == "open" else "⚪"
        label = f"{mark} #{c['id']} · {c.get('item_title', '—')[:24]}"
        rows.append([InlineKeyboardButton(label, callback_data=f"adm:cmp:open:{c['id']}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="adm:home")])
    await query.edit_message_text("🚨 **Жалобы**:", parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(rows))


async def adm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    svc.states.set(update.effective_user.id, "admin_broadcast")
    await query.edit_message_text(
        "📢 **Рассылка**\n\nВведи текст сообщения для всех пользователей бота.",
        parse_mode="Markdown", reply_markup=_back_to("home"))


async def adm_texts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    keys = list(TEXTS_DEFAULTS.keys())
    rows = []
    row = []
    for key in keys:
        row.append(InlineKeyboardButton(key, callback_data=f"adm:text:edit:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("« Назад", callback_data="adm:home")])
    await query.edit_message_text(
        "📝 **Тексты бота**\nВыбери текст для изменения:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))


async def adm_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    hidden = svc.db.settings.get("hidden_categories", [])
    rows = []
    for slug, emoji, name in CATEGORIES:
        mark = "🙈 Скрыта" if slug in hidden else "✅"
        rows.append([InlineKeyboardButton(f"{emoji} {name} — {mark}",
                                          callback_data=f"adm:cat:toggle:{slug}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="adm:home")])
    await query.edit_message_text("🗂️ **Категории**\nНажми, чтобы скрыть/показать:",
                                  parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))


async def adm_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    s = svc.db.settings
    toggle = "Вкл" if s.get("notify_new_user", True) else "Выкл"
    rows = [
        [InlineKeyboardButton(f"Лимит поисков: {s.get('search_limit', 3)}", callback_data="adm:set:search_limit")],
        [InlineKeyboardButton(f"Окно лимита, сек: {s.get('search_window', 60)}", callback_data="adm:set:search_window")],
        [InlineKeyboardButton(f"Объектов на страницу: {s.get('result_page_size', 5)}", callback_data="adm:set:result_page_size")],
        [InlineKeyboardButton(f"Страниц каталога за поиск: {s.get('fetch_pages', 1)}", callback_data="adm:set:fetch_pages")],
        [InlineKeyboardButton(f"Уведомл. о новом юзере: {toggle}", callback_data="adm:set:notify_new_user")],
        [InlineKeyboardButton("« Назад", callback_data="adm:home")],
    ]
    await query.edit_message_text("⚙️ **Настройки**\nЗначение меняется вводом нового числа:",
                                  parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))


async def adm_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lines = LOG_RING[-25:]
    text = "📋 **Логи**\n" + ("\n".join(lines) if lines else "Пока пусто.")
    if len(text) > 3800:
        text = text[:3800] + "\n..."
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_back_to("home"))


async def adm_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    blocked = [(int(k), v) for k, v in svc.db.users.items() if v.get("blocked")]
    if not blocked:
        await query.edit_message_text("🚫 Заблокированных нет.", reply_markup=_back_to("home"))
        return
    rows = []
    for uid, rec in blocked:
        name = rec.get("name") or rec.get("username") or uid
        rows.append([InlineKeyboardButton(f"{uid} · {name}",
                                          callback_data=f"adm:blk:unblock:{uid}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="adm:home")])
    await query.edit_message_text("🚫 **Блокировки**\nНажми, чтобы разблокировать:",
                                  parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))


# ---------------------------------------------------------------- обработчики

async def on_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    if not is_admin(uid):
        await query.answer("⛔ Доступ запрещён.")
        return
    svc.states.clear(uid)  # выход из режима ввода

    if data == "adm:home":
        await show_admin_panel(update, context)
        return
    if data == "adm:users":
        await adm_users(update, context)
        return
    if data == "adm:stats":
        await adm_stats(update, context)
        return
    if data == "adm:sstats":
        await adm_search_stats(update, context)
        return
    if data == "adm:support":
        await adm_support(update, context)
        return
    if data == "adm:complaints":
        await adm_complaints(update, context)
        return
    if data == "adm:bcast":
        await adm_broadcast(update, context)
        return
    if data == "adm:texts":
        await adm_texts(update, context)
        return
    if data == "adm:cats":
        await adm_categories(update, context)
        return
    if data == "adm:settings":
        await adm_settings(update, context)
        return
    if data == "adm:logs":
        await adm_logs(update, context)
        return
    if data == "adm:blocklist":
        await adm_blocklist(update, context)
        return

    if data == "adm:bcast:send":
        text = getattr(svc, "broadcast_pending", None)
        if not text:
            await query.answer("Нет текста для рассылки.")
            return
        delivered, failed = 0, 0
        for key, rec in list(svc.db.users.items()):
            if rec.get("blocked"):
                continue
            try:
                await context.bot.send_message(int(key), text, parse_mode="HTML")
                delivered += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)
        svc.broadcast_pending = None
        log_line(f"broadcast delivered={delivered} failed={failed}")
        wtext = f"📢 Рассылка завершена\n✅ доставлено: {delivered}\n❌ ошибок: {failed}"
        try:
            await query.edit_message_text(wtext, reply_markup=_back_to("home"))
        except Exception:
            await query.message.reply_text(wtext, reply_markup=_back_to("home"))
        return

    if data.startswith("adm:blk:direct:"):
        bid = int(data.split(":", 3)[3])
        rec = svc.db.users.get(str(bid))
        if rec:
            rec["blocked"] = True
            await svc.db.save_all()
            await query.answer(f"Пользователь {bid} заблокирован.")
        else:
            await query.answer("Пользователь не найден.")
        await adm_users(update, context)
        return

    if data.startswith("adm:usr:find"):
        svc.states.set(uid, "admin_find")
        await query.edit_message_text("Введи **ID** или **@username** пользователя:",
                                      parse_mode="Markdown", reply_markup=_back_to("users"))
        return
    if data == "adm:usr:block":
        svc.states.set(uid, "admin_block")
        await query.edit_message_text("Введи **ID** или **@username** для блокировки:",
                                      parse_mode="Markdown", reply_markup=_back_to("users"))
        return
    if data == "adm:usr:unblock":
        svc.states.set(uid, "admin_unblock")
        await query.edit_message_text("Введи **ID** или **@username** для разблокировки:",
                                      parse_mode="Markdown", reply_markup=_back_to("users"))
        return

    if data.startswith("adm:sup:open:"):
        tid = int(data.split(":", 3)[3])
        await _ticket_card(query, context, tid)
        return
    if data.startswith("adm:sup:reply:"):
        tid = int(data.split(":", 3)[3])
        svc.states.set(uid, "admin_reply", tid)
        await query.edit_message_text(f"Введи текст ответа по тикету **#{tid}**:",
                                      parse_mode="Markdown", reply_markup=_back_to("support"))
        return
    if data.startswith("adm:sup:close:"):
        tid = int(data.split(":", 3)[3])
        for t in svc.db.tickets:
            if t["id"] == tid and t["status"] == "open":
                t["status"] = "closed"
                svc.stats.close_ticket()
                await svc.db.save_all()
                await query.answer("Тикет закрыт.")
                break
        await adm_support(update, context)
        return

    if data.startswith("adm:cmp:open:"):
        cid = int(data.split(":", 3)[3])
        await _complaint_card(query, context, cid)
        return
    if data.startswith("adm:cmp:close:"):
        cid = int(data.split(":", 3)[3])
        for c in svc.db.complaints:
            if c["id"] == cid and c["status"] == "open":
                c["status"] = "closed"
                svc.stats.close_complaint()
                await svc.db.save_all()
                await query.answer("Отмечено обработанным.")
                break
        await adm_complaints(update, context)
        return

    if data.startswith("adm:blk:unblock:"):
        bid = int(data.split(":", 3)[3])
        rec = svc.db.users.get(str(bid))
        if rec:
            rec["blocked"] = False
            await svc.db.save_all()
            await query.answer(f"Пользователь {bid} разблокирован.")
        await adm_blocklist(update, context)
        return

    if data.startswith("adm:cat:toggle:"):
        slug = data.split(":", 3)[3]
        hidden = svc.db.settings.get("hidden_categories", [])
        if slug in hidden:
            hidden.remove(slug)
        else:
            hidden.append(slug)
        svc.db.settings["hidden_categories"] = hidden
        svc.service.hidden_categories = hidden
        await svc.db.save_all()
        await adm_categories(update, context)
        return

    if data.startswith("adm:set:"):
        key = data.split(":", 2)[2]
        if key == "notify_new_user":
            svc.db.settings[key] = not svc.db.settings.get(key, True)
            await svc.db.save_all()
            await adm_settings(update, context)
            return
        svc.states.set(uid, "admin_setting", key)
        await query.edit_message_text(
            f"Введи новое значение для **{key}** (сейчас: {svc.db.settings.get(key, SETTINGS_DEFAULTS.get(key))}):",
            parse_mode="Markdown", reply_markup=_back_to("settings"))
        return

    if data.startswith("adm:text:edit:"):
        key = data.split(":", 3)[3]
        svc.states.set(uid, "admin_text", key)
        current = svc.db.texts.get(key, "")
        await query.edit_message_text(
            f"📝 Редактируем **{key}**\nТекущий текст:\n<code>{_safe(current[:400])}</code>\n\n"
            f"Пришли новый текст (до 800 символов):",
            parse_mode="HTML", reply_markup=_back_to("texts"))
        return

    await query.answer()


def _safe(text: str) -> str:
    import html as _h
    return _h.escape(text)


async def _ticket_card(query, context: ContextTypes.DEFAULT_TYPE, tid: int) -> None:
    t = next((x for x in svc.db.tickets if x["id"] == tid), None)
    if t is None:
        await query.answer("Тикет не найден.")
        return
    replies = "\n".join(f"↩️ {r['text'][:100]}" for r in t.get("replies", [])) or "нет"
    text = (f"📨 Тикет **#{tid}** ({'открыт' if t['status'] == 'open' else 'закрыт'})\n"
            f"Пользователь: {t['user_id']}\n"
            f"@{t.get('username') or ''}\n\n"
            f"Текст:\n{t['text'][:700]}\n\n"
            f"Ответы:\n{replies}")
    rows = []
    if t["status"] == "open":
        rows.append([InlineKeyboardButton("💬 Ответить", callback_data=f"adm:sup:reply:{tid}"),
                     InlineKeyboardButton("Закрыть", callback_data=f"adm:sup:close:{tid}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="adm:support")])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))


async def _complaint_card(query, context: ContextTypes.DEFAULT_TYPE, cid: int) -> None:
    c = next((x for x in svc.db.complaints if x["id"] == cid), None)
    if c is None:
        await query.answer("Жалоба не найдена.")
        return
    link = c.get("item_link") or ""
    title = _safe(c.get("item_title", "—"))
    if link:
        title = f'<a href="{link}">{title}</a>'
    text = (f"🚨 Жалоба **#{cid}** ({c['status']})\n"
            f"Пользователь: {c.get('user_id')} @{c.get('username') or ''}\n"
            f"Объект: {title}\n"
            f"Причина: {c.get('reason')}\n"
            f"Время: {time.strftime('%d.%m %H:%M', time.localtime(c.get('ts', 0)))}")
    rows = []
    if c["status"] == "open":
        rows.append([InlineKeyboardButton("✅ Отметить обработанной", callback_data=f"adm:cmp:close:{cid}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="adm:complaints")])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


# ---------------------------------------------------------------- ввод админа

async def on_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    state = svc.states.get(uid)
    if not state:
        return

    mode = state[0]

    if mode == "admin_find":
        svc.states.clear(uid)
        found_uid, rec = find_user(text)
        if found_uid is None:
            await update.message.reply_text("Пользователь не найден.")
            return
        if rec is None:
            await update.message.reply_text(f"Пользователь {found_uid} ещё не зарегистрирован.")
            return
        rows = [[InlineKeyboardButton("🚫 Заблокировать", callback_data=f"adm:blk:direct:{found_uid}")]] \
            if not rec.get("blocked") else \
            [[InlineKeyboardButton("🔓 Разблокировать", callback_data=f"adm:blk:unblock:{found_uid}")]]
        rows.append([InlineKeyboardButton("« Назад", callback_data="adm:users")])
        await update.message.reply_text(_user_line(found_uid, rec), parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(rows))
        return

    if mode == "admin_block":
        svc.states.clear(uid)
        found_uid, rec = find_user(text)
        if found_uid is None:
            await update.message.reply_text("Пользователь не найден.")
            return
        if rec:
            rec["blocked"] = True
            await svc.db.save_all()
            await update.message.reply_text(f"🚫 Пользователь {found_uid} заблокирован.")
        else:
            svc.db.users[str(found_uid)] = {"first_seen": 0, "last_seen": 0, "name": "",
                                            "username": "", "blocked": True}
            await svc.db.save_all()
            await update.message.reply_text(f"🚫 Пользователь {found_uid} заблокирован (превентивно).")
        return

    if mode == "admin_unblock":
        svc.states.clear(uid)
        found_uid, rec = find_user(text)
        if found_uid is None or rec is None:
            await update.message.reply_text("Пользователь не найден.")
            return
        rec["blocked"] = False
        await svc.db.save_all()
        await update.message.reply_text(f"🔓 Пользователь {found_uid} разблокирован.")
        return

    if mode == "admin_reply":
        ticket_id = state[1]
        svc.states.clear(uid)
        t = next((x for x in svc.db.tickets if x["id"] == ticket_id), None)
        if t is None:
            await update.message.reply_text("Тикет не найден.")
            return
        user_id = t["user_id"]
        t.setdefault("replies", []).append({"ts": int(time.time()), "text": text[:2000]})
        await svc.db.save_all()
        try:
            await context.bot.send_message(user_id, text, parse_mode="HTML")
            await notifications.reply_delivered(context, user_id, ticket_id)
        except Exception as exc:
            log.warning("reply delivery failed: %s", exc)
            await notifications.reply_failed(context, user_id, ticket_id)
        await update.message.reply_text(f"Ответ отправлен по тикету #{ticket_id}.")
        return

    if mode == "admin_broadcast":
        svc.states.clear(uid)
        text = text.strip()
        if not text or len(text) > 2000:
            await update.message.reply_text("Текст пустой или слишком длинный. Отменено.")
            return
        confirm_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📨 Отправить всем", callback_data="adm:bcast:send")],
            [InlineKeyboardButton("Отмена", callback_data="adm:home")],
        ])
        svc.broadcast_pending = text
        await update.message.reply_text(
            f"📢 Предпросмотр рассылки:\n\n{text}\n\n"
            f"Пользователей: {len(svc.db.users)}", parse_mode="Markdown", reply_markup=confirm_markup)
        return

    if mode == "admin_text":
        key = state[1]
        svc.states.clear(uid)
        new_text = text.strip()[:800]
        if not new_text:
            await update.message.reply_text("Текст пустой. Отменено.")
            return
        svc.db.texts[key] = new_text
        await svc.db.save_all()
        await update.message.reply_text(f"✅ Текст **{key}** сохранён.")
        return

    if mode == "admin_setting":
        key = state[1]
        svc.states.clear(uid)
        try:
            val = int(text.strip())
            if val <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Нужно целое число больше 0. Отменено.")
            return
        svc.db.settings[key] = val
        await _apply_settings()
        await svc.db.save_all()
        await update.message.reply_text(f"✅ **{key}** = {val}")
        return


def _apply_settings() -> None:
    s = svc.db.settings
    svc.limiter.set_window(s.get("search_limit", 3), s.get("search_window", 60))