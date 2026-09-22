"""Форматирование результатов для сообщений бота."""
from __future__ import annotations

import html
from typing import Any

TYPE_EMOJI = {
    "chat": "👥",
    "channel": "📢",
    "bot": "🤖",
}

TYPE_LABEL = {
    "chat": "Группа",
    "channel": "Канал",
    "bot": "Бот",
}


def format_count(n: int | float | None) -> str | None:
    """8_400 -> '8.4K', 1_234_567 -> '1.2M'."""
    if n is None or n is False:
        return None
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        val = n / 1000.0
        return (f"{val:.1f}K" if val < 100 else f"{int(val)}K").replace(".0K", "K")
    val = n / 1_000_000.0
    return f"{val:.1f}M".replace(".0M", "M")


def esc(text: Any) -> str:
    return html.escape(str(text))


def type_label(item: dict) -> str:
    etype = item.get("type", "channel")
    return f"{TYPE_EMOJI.get(etype, '📢')} {TYPE_LABEL.get(etype, 'Объект')}"


def item_size(item: dict) -> int | None:
    return item.get("size")


def item_line(item: dict) -> str:
    """Подпись под названием: тип · размер (если есть)."""
    parts = [type_label(item)]
    size = format_count(item_size(item))
    if size:
        parts.append(size)
    return " · ".join(parts)


def result_line(item: dict) -> str:
    """Одна строка результата в списке."""
    title = esc(item.get("title", "—"))
    if item.get("link"):
        # Название кликабельно и открывает объект прямо в Telegram
        title = f'<a href="{esc(item["link"])}">{title}</a>'
    sub = esc(item_line(item))
    return f"{title}\n{sub}"


def build_results_text(header: str, items: list[dict]) -> str:
    lines = [header]
    for it in items:
        lines.append("")
        lines.append(result_line(it))
    return "\n".join(lines)