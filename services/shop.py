"""Сервис магазина: товары и покупки за баллы.

Товары двух типов:
  - auto   — бот выполняет действие сам (например, снять варн).
  - manual — бот пишет в группу, админ выполняет вручную.
"""
from __future__ import annotations

from sqlalchemy import select

from database.models import ShopItem
from database.session import get_session

# известные авто-действия
AUTO_ACTIONS = {
    "remove_warn": "снять 1 варн",
}


async def add_item(
    chat_id: int,
    kind: str,
    price: int,
    name: str,
    description: str | None = None,
    action: str | None = None,
) -> ShopItem:
    async with get_session() as session:
        item = ShopItem(
            chat_id=chat_id,
            kind=kind,
            price=price,
            name=name,
            description=description,
            action=action,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item


async def remove_item(chat_id: int, ident: str) -> bool:
    """Удаляет товар по ID (число) или по названию."""
    async with get_session() as session:
        if ident.isdigit():
            item = await session.scalar(
                select(ShopItem).where(
                    ShopItem.chat_id == chat_id, ShopItem.id == int(ident)
                )
            )
        else:
            item = await session.scalar(
                select(ShopItem).where(
                    ShopItem.chat_id == chat_id, ShopItem.name.ilike(ident)
                )
            )
        if item is None:
            return False
        await session.delete(item)
        await session.commit()
        return True


async def list_items(chat_id: int) -> list[ShopItem]:
    async with get_session() as session:
        rows = await session.scalars(
            select(ShopItem).where(ShopItem.chat_id == chat_id).order_by(ShopItem.price)
        )
        return list(rows)


async def get_item(chat_id: int, item_id: int) -> ShopItem | None:
    async with get_session() as session:
        return await session.scalar(
            select(ShopItem).where(
                ShopItem.chat_id == chat_id, ShopItem.id == item_id
            )
        )
