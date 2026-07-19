"""Сервис модерации: варны, история наказаний.

Сами Telegram-действия (mute/kick/ban) выполняет хендлер через Bot API;
здесь — только учёт в БД (варны, лог наказаний, авто-бан на 3 варна).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from database.models import Punishment
from database.session import get_session

WARN_LIMIT = 3  # на 3-м варне — авто-бан


async def add_punishment(
    chat_id: int,
    user_id: int,
    kind: str,
    issued_by: int,
    reason: str | None = None,
    until: datetime | None = None,
) -> None:
    """Записывает наказание в историю."""
    async with get_session() as session:
        session.add(
            Punishment(
                chat_id=chat_id,
                user_id=user_id,
                kind=kind,
                reason=reason,
                issued_by=issued_by,
                until=until,
                active=True,
            )
        )
        await session.commit()


async def add_warn(
    chat_id: int, user_id: int, issued_by: int, reason: str | None = None
) -> int:
    """Добавляет варн. Возвращает текущее количество активных варнов."""
    async with get_session() as session:
        session.add(
            Punishment(
                chat_id=chat_id,
                user_id=user_id,
                kind="warn",
                reason=reason,
                issued_by=issued_by,
                active=True,
            )
        )
        await session.commit()
        # вернём число активных варнов
        return await _count_active_warns(session, chat_id, user_id)


async def _count_active_warns(session, chat_id: int, user_id: int) -> int:
    from sqlalchemy import func

    return await session.scalar(
        select(func.count())
        .select_from(Punishment)
        .where(
            Punishment.chat_id == chat_id,
            Punishment.user_id == user_id,
            Punishment.kind == "warn",
            Punishment.active == True,  # noqa: E712
        )
    ) or 0


async def count_active_warns(chat_id: int, user_id: int) -> int:
    async with get_session() as session:
        return await _count_active_warns(session, chat_id, user_id)


async def remove_last_warn(chat_id: int, user_id: int) -> bool:
    """Снимает последний активный варн. False — если варнов нет."""
    async with get_session() as session:
        warn = await session.scalar(
            select(Punishment)
            .where(
                Punishment.chat_id == chat_id,
                Punishment.user_id == user_id,
                Punishment.kind == "warn",
                Punishment.active == True,  # noqa: E712
            )
            .order_by(Punishment.created_at.desc())
            .limit(1)
        )
        if warn is None:
            return False
        warn.active = False
        await session.commit()
        return True


async def get_history(chat_id: int, user_id: int) -> list[Punishment]:
    """Полная история наказаний пользователя (свежие сверху)."""
    async with get_session() as session:
        rows = await session.scalars(
            select(Punishment)
            .where(Punishment.chat_id == chat_id, Punishment.user_id == user_id)
            .order_by(Punishment.created_at.desc())
        )
        return list(rows)


async def clear_active_warns(chat_id: int, user_id: int) -> None:
    """Гасит все активные варны (после авто-бана)."""
    async with get_session() as session:
        warns = await session.scalars(
            select(Punishment).where(
                Punishment.chat_id == chat_id,
                Punishment.user_id == user_id,
                Punishment.kind == "warn",
                Punishment.active == True,  # noqa: E712
            )
        )
        for w in warns:
            w.active = False
        await session.commit()
