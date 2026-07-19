"""Разбор цели команды: reply / @username / числовой ID.

Возвращает user_id цели и остаток аргументов (причина, время и т.п.).
username резолвится через БД (тех, кто уже писал в чате) — как и просил
пользователь: люди попадают в базу при первом сообщении.
"""
from __future__ import annotations

from aiogram.types import Message
from sqlalchemy import select

from database.models import User
from database.session import get_session


async def resolve_target(message: Message) -> tuple[int | None, list[str]]:
    """Определяет цель команды.

    Приоритет:
      1. reply на сообщение -> автор reply.
      2. первый аргумент @username или числовой ID.

    Возвращает (user_id | None, оставшиеся_слова).
    Слова после цели — это причина/время/сумма (парсит вызывающий код).
    """
    # текст без самой команды (первое слово)
    parts = (message.text or message.caption or "").split()
    args = parts[1:] if parts else []

    # 1) reply имеет приоритет
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id, args

    # 2) первый аргумент как цель
    if args:
        target = args[0]
        # числовой ID
        if target.lstrip("-").isdigit():
            return int(target), args[1:]
        # @username
        if target.startswith("@"):
            uid = await _resolve_username(target[1:])
            if uid is not None:
                return uid, args[1:]

    return None, args


async def _resolve_username(username: str) -> int | None:
    """Ищет user_id по username среди известных боту пользователей."""
    async with get_session() as session:
        row = await session.scalar(
            select(User.id).where(User.username.ilike(username))
        )
        return row


def parse_amount(args: list[str]) -> tuple[int | None, list[str]]:
    """Извлекает число (баллы) из начала args. Возвращает (число|None, остаток)."""
    if args and args[0].lstrip("-").isdigit():
        return int(args[0]), args[1:]
    return None, args
