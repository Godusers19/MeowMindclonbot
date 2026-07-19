"""Inline-клавиатура управления правами кэпа."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Cap
from services.caps import CAP_PERMISSIONS


def cap_rights_keyboard(chat_id: int, user_id: int, cap: Cap) -> InlineKeyboardMarkup:
    """Кнопки-переключатели прав + кнопка «Готово».

    callback_data: capperm:<chat_id>:<user_id>:<flag>
                   capdone:<chat_id>:<user_id>
    """
    rows = []
    for flag, title in CAP_PERMISSIONS.items():
        enabled = getattr(cap, flag)
        mark = "✅" if enabled else "❌"
        rows.append([
            InlineKeyboardButton(
                text=f"{mark} {title}",
                callback_data=f"capperm:{chat_id}:{user_id}:{flag}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="💾 Готово",
            callback_data=f"capdone:{chat_id}:{user_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
