"""Система прав: владелец бота, создатель/админ чата, кэпы с флагами.

Иерархия:
  - owner (OWNER_ID) — может всё, везде.
  - создатель чата (Telegram creator) — может всё в своём чате.
  - Telegram-админ — модерация, ЕСЛИ не включён режим only_caps.
  - кэп — действия по своим флагам (can_warn/mute/kick/ban/points).
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select

from config import config
from database.models import Cap, Chat
from database.session import get_session

# карта: действие -> имя флага в модели Cap
CAP_FLAGS = {
    "warn": "can_warn",
    "mute": "can_mute",
    "kick": "can_kick",
    "ban": "can_ban",
    "points": "can_points",
}


async def is_owner(user_id: int) -> bool:
    return config.owner_id != 0 and user_id == config.owner_id


async def is_chat_creator(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status == "creator"
    except Exception:  # noqa: BLE001
        return False


async def is_tg_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:  # noqa: BLE001
        return False


async def get_cap(chat_id: int, user_id: int) -> Cap | None:
    async with get_session() as session:
        return await session.scalar(
            select(Cap).where(Cap.chat_id == chat_id, Cap.user_id == user_id)
        )


async def _only_caps_enabled(chat_id: int) -> bool:
    async with get_session() as session:
        return bool(
            await session.scalar(
                select(Chat.only_caps).where(Chat.id == chat_id)
            )
        )


async def can_do(bot: Bot, message: Message, action: str) -> bool:
    """Проверяет, вправе ли автор сообщения выполнить действие.

    action: warn / mute / kick / ban / points.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id

    # 1) владелец бота и создатель чата — всегда да
    if await is_owner(user_id):
        return True
    if await is_chat_creator(bot, chat_id, user_id):
        return True

    # 2) кэп — по своему флагу
    cap = await get_cap(chat_id, user_id)
    if cap is not None:
        flag = CAP_FLAGS.get(action)
        return bool(getattr(cap, flag, False)) if flag else False

    # 3) обычный TG-админ — только если режим only_caps выключен
    if await _only_caps_enabled(chat_id):
        return False
    return await is_tg_admin(bot, chat_id, user_id)
