"""Сервис интерактивных списков: CRUD шаблонов.

Шаблон — текст с плейсхолдерами {user} (место игрока) и {cap} (место капитана).
При вызове .список рендерится «живой» список, где места занимают кнопками.
Занятость активного списка живёт в памяти (services/list_runtime.py).
"""
from __future__ import annotations

from sqlalchemy import delete, select

from database.models import ListTemplate
from database.session import get_session


async def save_template(
    chat_id: int, number: int, template: str, owner_id: int, cap_limit: int = 0
) -> None:
    """Создаёт или перезаписывает шаблон списка с данным номером."""
    async with get_session() as session:
        existing = await session.scalar(
            select(ListTemplate).where(
                ListTemplate.chat_id == chat_id, ListTemplate.number == number
            )
        )
        if existing:
            existing.template = template
            existing.cap_limit = cap_limit
            existing.owner_id = owner_id
        else:
            session.add(
                ListTemplate(
                    chat_id=chat_id,
                    number=number,
                    template=template,
                    cap_limit=cap_limit,
                    owner_id=owner_id,
                )
            )
        await session.commit()


async def get_template(chat_id: int, number: int) -> ListTemplate | None:
    async with get_session() as session:
        return await session.scalar(
            select(ListTemplate).where(
                ListTemplate.chat_id == chat_id, ListTemplate.number == number
            )
        )


async def delete_template(chat_id: int, number: int) -> bool:
    async with get_session() as session:
        tpl = await session.scalar(
            select(ListTemplate).where(
                ListTemplate.chat_id == chat_id, ListTemplate.number == number
            )
        )
        if tpl is None:
            return False
        await session.delete(tpl)
        await session.commit()
        return True


async def list_numbers(chat_id: int) -> list[int]:
    async with get_session() as session:
        rows = await session.scalars(
            select(ListTemplate.number)
            .where(ListTemplate.chat_id == chat_id)
            .order_by(ListTemplate.number)
        )
        return list(rows)
