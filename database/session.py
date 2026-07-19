"""Асинхронная сессия SQLAlchemy и инициализация БД."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import config
from database.models import Base

engine = create_async_engine(config.database_url, echo=False)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Создаёт таблицы, если их ещё нет (для старта без Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session() -> AsyncSession:
    """Возвращает новую сессию. Используй как `async with get_session() as s:`."""
    return async_session()
