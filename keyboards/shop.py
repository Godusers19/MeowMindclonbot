"""Inline-клавиатура магазина: кнопка «Купить» на каждый товар."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import ShopItem


def shop_keyboard(items: list[ShopItem]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"🛒 {item.name} — {item.price} б.",
            callback_data=f"buy:{item.chat_id}:{item.id}",
        )]
        for item in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
