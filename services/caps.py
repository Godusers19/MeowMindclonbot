"""Сервис кэпов: назначение, снятие, права (флаги), режимы чата."""
from __future__ import annotations

from sqlalchemy import delete, select

from database.models import Cap, Chat
from database.session import get_session

# флаги прав и их подписи для кнопок
CAP_PERMISSIONS = {
    "can_warn": "Варн",
    "can_mute": "Мут",
    "can_kick": "Кик",
    "can_ban": "Бан",
    "can_points": "Баллы",
}


async def add_cap(chat_id: int, user_id: int) -> bool:
    """Назначает кэпа со всеми правами. False — если уже кэп."""
    async with get_session() as session:
        exists = await session.scalar(
            select(Cap).where(Cap.chat_id == chat_id, Cap.user_id == user_id)
        )
        if exists:
            return False
        session.add(Cap(chat_id=chat_id, user_id=user_id))
        await session.commit()
        return True


async def remove_cap(chat_id: int, user_id: int) -> bool:
    async with get_session() as session:
        cap = await session.scalar(
            select(Cap).where(Cap.chat_id == chat_id, Cap.user_id == user_id)
        )
        if cap is None:
            return False
        await session.delete(cap)
        await session.commit()
        return True


async def get_cap(chat_id: int, user_id: int) -> Cap | None:
    async with get_session() as session:
        return await session.scalar(
            select(Cap).where(Cap.chat_id == chat_id, Cap.user_id == user_id)
        )


async def list_caps(chat_id: int) -> list[Cap]:
    async with get_session() as session:
        rows = await session.scalars(select(Cap).where(Cap.chat_id == chat_id))
        return list(rows)


async def toggle_permission(chat_id: int, user_id: int, flag: str) -> Cap | None:
    """Переключает флаг права у кэпа. Возвращает обновлённого кэпа."""
    if flag not in CAP_PERMISSIONS:
        return None
    async with get_session() as session:
        cap = await session.scalar(
            select(Cap).where(Cap.chat_id == chat_id, Cap.user_id == user_id)
        )
        if cap is None:
            return None
        setattr(cap, flag, not getattr(cap, flag))
        await session.commit()
        await session.refresh(cap)
        return cap


async def reset_caps(chat_id: int) -> int:
    """Удаляет всех кэпов чата. Возвращает число удалённых."""
    async with get_session() as session:
        caps = list(await session.scalars(select(Cap).where(Cap.chat_id == chat_id)))
        count = len(caps)
        await session.execute(delete(Cap).where(Cap.chat_id == chat_id))
        await session.commit()
        return count


# ─── Режимы чата ────────────────────────────────────────────

async def toggle_only_caps(chat_id: int) -> bool:
    """Переключает режим «только кэпы». Возвращает новое значение."""
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            chat = Chat(id=chat_id)
            session.add(chat)
        chat.only_caps = not chat.only_caps
        await session.commit()
        return chat.only_caps


async def toggle_transfer(chat_id: int) -> bool:
    """Переключает передачу баллов между участниками."""
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            chat = Chat(id=chat_id)
            session.add(chat)
        chat.allow_transfer = not chat.allow_transfer
        await session.commit()
        return chat.allow_transfer
