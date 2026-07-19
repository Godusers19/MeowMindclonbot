"""Сервис игр и опросов: расписание игр, шаблоны опросов."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from database.models import Game, PollTemplate
from database.session import get_session
from utils.now import utcnow


# ─── Игры ───────────────────────────────────────────────────

async def add_game(chat_id: int, starts_at: datetime, description: str) -> Game:
    async with get_session() as session:
        game = Game(chat_id=chat_id, starts_at=starts_at, description=description)
        session.add(game)
        await session.commit()
        await session.refresh(game)
        return game


async def list_games(chat_id: int) -> list[Game]:
    """Будущие игры чата, отсортированные по времени."""
    async with get_session() as session:
        rows = await session.scalars(
            select(Game)
            .where(Game.chat_id == chat_id, Game.starts_at >= utcnow())
            .order_by(Game.starts_at)
        )
        return list(rows)


async def cancel_game(chat_id: int, starts_at: datetime) -> bool:
    async with get_session() as session:
        game = await session.scalar(
            select(Game).where(
                Game.chat_id == chat_id, Game.starts_at == starts_at
            )
        )
        if game is None:
            return False
        await session.delete(game)
        await session.commit()
        return True


async def all_future_games() -> list[Game]:
    """Все будущие игры (для восстановления напоминаний при старте)."""
    async with get_session() as session:
        rows = await session.scalars(
            select(Game).where(Game.starts_at >= utcnow())
        )
        return list(rows)


# ─── Шаблоны опросов ────────────────────────────────────────

async def save_poll(
    chat_id: int,
    name: str,
    question: str,
    options: list[str],
    schedule: str | None = None,
) -> None:
    async with get_session() as session:
        existing = await session.scalar(
            select(PollTemplate).where(
                PollTemplate.chat_id == chat_id, PollTemplate.name == name
            )
        )
        if existing:
            existing.question = question
            existing.options = json.dumps(options, ensure_ascii=False)
            existing.schedule = schedule
        else:
            session.add(
                PollTemplate(
                    chat_id=chat_id,
                    name=name,
                    question=question,
                    options=json.dumps(options, ensure_ascii=False),
                    schedule=schedule,
                )
            )
        await session.commit()


async def get_poll(chat_id: int, name: str) -> tuple[str, list[str]] | None:
    async with get_session() as session:
        tpl = await session.scalar(
            select(PollTemplate).where(
                PollTemplate.chat_id == chat_id, PollTemplate.name == name
            )
        )
        if tpl is None:
            return None
        return tpl.question, json.loads(tpl.options)


async def list_polls(chat_id: int) -> list[str]:
    async with get_session() as session:
        rows = await session.scalars(
            select(PollTemplate.name).where(PollTemplate.chat_id == chat_id)
        )
        return list(rows)
