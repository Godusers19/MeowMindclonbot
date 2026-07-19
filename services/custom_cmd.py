"""Сервис кастомных команд: триггеры, алиасы, медиа.

Одна команда (CustomCommand) = триггер + опциональное медиа + список
вариантов ответа (CommandAlias). Первый вариант — основной (is_primary).
При вызове .триггер бот случайно выбирает один из вариантов.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.models import CommandAlias, CustomCommand
from database.session import get_session


async def create_command(
    chat_id: int,
    trigger: str,
    text: str,
    media_type: str | None = None,
    media_id: str | None = None,
) -> bool:
    """Создаёт команду с основным вариантом ответа.

    Возвращает False, если триггер уже занят.
    """
    async with get_session() as session:
        exists = await session.scalar(
            select(CustomCommand).where(
                CustomCommand.chat_id == chat_id, CustomCommand.trigger == trigger
            )
        )
        if exists:
            return False
        cmd = CustomCommand(
            chat_id=chat_id,
            trigger=trigger,
            media_type=media_type,
            media_id=media_id,
        )
        cmd.aliases.append(CommandAlias(text=text, is_primary=True))
        session.add(cmd)
        await session.commit()
        return True


async def add_alias(chat_id: int, trigger: str, text: str) -> bool:
    """Добавляет доп. вариант ответа. False — если команды нет."""
    async with get_session() as session:
        cmd = await session.scalar(
            select(CustomCommand).where(
                CustomCommand.chat_id == chat_id, CustomCommand.trigger == trigger
            )
        )
        if cmd is None:
            return False
        session.add(CommandAlias(command_id=cmd.id, text=text, is_primary=False))
        await session.commit()
        return True


async def get_command(chat_id: int, trigger: str) -> CustomCommand | None:
    async with get_session() as session:
        return await session.scalar(
            select(CustomCommand)
            .options(selectinload(CustomCommand.aliases))
            .where(
                CustomCommand.chat_id == chat_id, CustomCommand.trigger == trigger
            )
        )


async def list_aliases(chat_id: int, trigger: str) -> list[CommandAlias]:
    cmd = await get_command(chat_id, trigger)
    if cmd is None:
        return []
    # основной первым, затем остальные по id
    return sorted(cmd.aliases, key=lambda a: (not a.is_primary, a.id))


async def delete_alias(chat_id: int, trigger: str, number: int) -> str:
    """Удаляет вариант по номеру (1 — основной, его удалить нельзя).

    Возвращает: "ok" / "primary" / "not_found" / "bad_number".
    """
    aliases = await list_aliases(chat_id, trigger)
    if not aliases:
        return "not_found"
    if number == 1:
        return "primary"
    if number < 1 or number > len(aliases):
        return "bad_number"
    target = aliases[number - 1]
    async with get_session() as session:
        obj = await session.get(CommandAlias, target.id)
        if obj:
            await session.delete(obj)
            await session.commit()
    return "ok"


async def delete_command(chat_id: int, trigger: str) -> bool:
    async with get_session() as session:
        cmd = await session.scalar(
            select(CustomCommand).where(
                CustomCommand.chat_id == chat_id, CustomCommand.trigger == trigger
            )
        )
        if cmd is None:
            return False
        await session.delete(cmd)
        await session.commit()
        return True


async def all_triggers(chat_id: int) -> list[str]:
    async with get_session() as session:
        rows = await session.scalars(
            select(CustomCommand.trigger).where(CustomCommand.chat_id == chat_id)
        )
        return list(rows)
