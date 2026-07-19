"""Разовая синхронизация участников через доступные методы Bot API.

Bot API НЕ отдаёт полный список участников — доступны только админы
(getChatAdministrators) и число участников (getChatMemberCount).
Эта функция подтягивает хотя бы админов в базу; остальные попадают
автоматически через middleware, когда пишут/входят.
"""
from __future__ import annotations

from aiogram import Bot

from database.session import get_session
from middlewares.registration import upsert_member


async def sync_admins(bot: Bot, chat_id: int, chat_title: str = "") -> int:
    """Заносит всех админов чата в базу. Возвращает число добавленных."""
    admins = await bot.get_chat_administrators(chat_id)
    count = 0
    async with get_session() as session:
        for m in admins:
            if m.user and not m.user.is_bot:
                await upsert_member(session, chat_id, chat_title, m.user)
                count += 1
        await session.commit()
    return count
