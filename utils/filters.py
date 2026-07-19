"""Фильтр текстовых команд с префиксами . + - (как у MeowMind).

Пример: TextCommand(".баллы") сработает на «.баллы» и «.баллы 5».
Команда — это первое слово сообщения (регистронезависимо).
"""
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message


class TextCommand(BaseFilter):
    def __init__(self, *commands: str):
        # приводим к нижнему регистру для сравнения
        self.commands = {c.lower() for c in commands}

    async def __call__(self, message: Message) -> bool:
        text = message.text or message.caption
        if not text:
            return False
        first = text.split(maxsplit=1)[0].lower()
        return first in self.commands
