"""Парсинг кастомных команд: кнопки-ссылки и подстановки.

Кнопки: {[Текст - https://ссылка]} в конце текста -> inline-кнопки.
Подстановки: {name}, {mention}, {sender_name}.
"""
from __future__ import annotations

import html
import re

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, User

# {[Текст - ссылка]}
_BUTTON_RE = re.compile(r"\{\[([^\]]+?)\s*-\s*(https?://[^\]]+?)\]\}")


def extract_buttons(text: str) -> tuple[str, InlineKeyboardMarkup | None]:
    """Вырезает кнопки-ссылки из текста, возвращает (чистый_текст, клавиатура)."""
    buttons = []
    for m in _BUTTON_RE.finditer(text):
        label, url = m.group(1).strip(), m.group(2).strip()
        buttons.append([InlineKeyboardButton(text=label, url=url)])
    clean = _BUTTON_RE.sub("", text).strip()
    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    return clean, kb


def apply_substitutions(
    text: str, target: User | None, sender: User
) -> str:
    """Подставляет {name}, {mention}, {sender_name}.

    target — цель (reply/аргумент), для {name}/{mention}; если нет — sender.
    """
    tgt = target or sender
    tgt_name = html.escape(tgt.first_name or "")
    mention = f'<a href="tg://user?id={tgt.id}">{tgt_name}</a>'
    sender_name = html.escape(sender.first_name or "")

    return (
        text.replace("{name}", tgt_name)
        .replace("{mention}", mention)
        .replace("{sender_name}", sender_name)
    )
