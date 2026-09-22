"""Редактируемые тексты бота и настройки по умолчанию."""
from __future__ import annotations

TEXTS_DEFAULTS: dict[str, str] = {
    "main_menu": (
        "🔎 **Найди нужную группу, канал или бота в Telegram.**\n"
        "Быстрый поиск по каталогу — без лишнего текста и сложной навигации."
    ),
    "search_menu": "🔎 Введи название, тему или ключевые слова — для более точного результата используй фильтры.",
    "smart_search_prompt": "🔎 Напиши запрос — например: minecraft, python, музыка, футбол, новости. Или нажми «Отмена».",
    "filters_title": "⚙️ **Поиск по фильтрам**\nВыбери параметры и нажми «Найти».",
    "results_header": "🔎 **Результаты поиска**",
    "no_results": "Ничего не нашлось. Попробуй другой запрос или измени фильтры.",
    "search_error": "⚠️ Сейчас поиск временно недоступен. Попробуй ещё раз через несколько секунд.",
    "limit_msg": "⏳ Лимит поиска достигнут.\nСледующий поиск будет доступен через **{seconds} сек**.",
    "support_prompt": "💬 Напиши сообщение — я передам его команде TeleSearch.",
    "support_sent": "✅ Сообщение передано команде. Мы ответим как можно быстрее.",
    "popular_title": "🔥 **Популярное**",
    "categories_title": "🗂️ **Категории**\nВыбери тему — я покажу популярные каналы и группы.",
    "random_title": "🎲 **Случайное**",
    "random_hint": "Нажми «🎲 Ещё» — и я покажу другой объект из каталога.",
    "blocked_msg": "⛔ Доступ ограничен. Если считаешь это ошибкой — напиши в поддержку.",
    "complaint_title": "⚠️ Жалоба",
    "complaint_sent": "Спасибо, жалоба передана. Команда проверит её в ближайшее время.",
}

SETTINGS_DEFAULTS: dict = {
    "search_limit": 3,
    "search_window": 60,
    "result_page_size": 5,
    "fetch_pages": 1,
    "notify_new_user": True,
    "hidden_categories": [],
}

# Категории TGDen: slug -> (эмодзи, название)
CATEGORIES: list[tuple[str, str, str]] = [
    ("news", "📰", "Новости"),
    ("tech", "💻", "Технологии"),
    ("ai", "🧠", "AI / ML"),
    ("gaming", "🎮", "Игры"),
    ("music", "🎵", "Музыка"),
    ("art", "🎨", "Искусство и дизайн"),
    ("sports", "⚽", "Спорт"),
    ("education", "📚", "Образование"),
    ("finance", "💼", "Финансы"),
    ("travel", "✈️", "Путешествия"),
    ("health", "🩺", "Здоровье"),
    ("humor", "😂", "Юмор"),
    ("entertainment", "🎬", "Развлечения"),
    ("science", "🔬", "Наука"),
    ("crypto", "🪙", "Криптовалюты"),
    ("marketing", "📣", "Маркетинг"),
    ("startups", "🚀", "Стартапы"),
    ("productivity", "✅", "Продуктивность"),
]

# Языки: код -> (флаг, название)
LANGUAGES: list[tuple[str, str, str]] = [
    ("ru", "🇷🇺", "Русский"),
    ("en", "🇬🇧", "English"),
    ("uk", "🇺🇦", "Українська"),
    ("tr", "🇹🇷", "Türkçe"),
    ("de", "🇩🇪", "Deutsch"),
    ("es", "🇪🇸", "Español"),
    ("fr", "🇫🇷", "Français"),
    ("it", "🇮🇹", "Italiano"),
    ("pt", "🇧🇷", "Português"),
    ("fa", "🇮🇷", "فارسی"),
    ("ar", "🇸🇦", "العربية"),
    ("hy", "🇦🇲", "Հայերեն"),
    ("uz", "🇺🇿", "Oʻzbekcha"),
    ("kk", "🇰🇿", "Қазақша"),
    ("be", "🇧🇾", "Беларуская"),
]

# Типы объектов: ключ -> (название, список типов)
TYPE_OPTIONS: list[tuple[str, str, list[str] | None]] = [
    ("all", "🔀 Группы + каналы + боты", None),
    ("chat", "👥 Группы", ["chat"]),
    ("channel", "📢 Каналы", ["channel"]),
    ("bot", "🤖 Боты", ["bot"]),
    ("chat+channel", "👥 + 📢 Группы и каналы", ["chat", "channel"]),
    ("chat+bot", "👥 + 🤖 Группы и боты", ["chat", "bot"]),
    ("channel+bot", "📢 + 🤖 Каналы и боты", ["channel", "bot"]),
]

# Размер аудитории: ключ -> (название, мин, макс)
SIZE_OPTIONS: list[tuple[str, str, int | None, int | None]] = [
    ("any", "Любое количество", None, None),
    ("lt1k", "До 1K", None, 1000),
    ("1k10k", "1K – 10K", 1000, 10000),
    ("10k100k", "10K – 100K", 10000, 100000),
    ("gt100k", "100K +", 100000, None),
]

# Причины жалобы: ключ -> текст
COMPLAINT_REASONS: list[tuple[str, str]] = [
    ("broken", "Ссылка не работает"),
    ("removed", "Группа/канал/бот удалён"),
    ("category", "Неправильная категория"),
    ("spam", "Спам"),
    ("other", "Другое"),
]


def type_label_by_key(key: str) -> str:
    for k, label, _ in TYPE_OPTIONS:
        if k == key:
            return label
    return "🔀 Все"


def size_label_by_key(key: str) -> str:
    for k, label, _, _ in SIZE_OPTIONS:
        if k == key:
            return label
    return "Любое количество"


def lang_label_by_code(code: str) -> str:
    for c, flag, name in LANGUAGES:
        if c == code:
            return f"{flag} {name}"
    return code