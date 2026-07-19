"""Middleware авто-регистрации (без userbot).

Bot API не умеет отдавать полный список участников группы, поэтому людей
собираем из всех апдейтов, где Telegram вообще раскрывает пользователя:

  - автор сообщения          (event.from_user)
  - тот, кому ответили        (reply_to_message.from_user)
  - упомянутые в тексте       (entities → text_mention.user)
  - вошедшие в группу         (new_chat_members)
  - апдейты ChatMemberUpdated (вступил/вышел — самый надёжный, нужен бот-админ)

Так база наполняется сама. Разово подтянуть админов можно кнопкой
«синхронизировать» в веб-панели/меню (getChatAdministrators).
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import ChatMemberUpdated, Message, User as TgUser
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database.models import Chat, ChatMember, User
from database.session import get_session

_GROUP_TYPES = ("group", "supergroup")


async def upsert_member(session, chat_id: int, chat_title: str, user: TgUser,
                        *, left: bool = False) -> None:
    """Заносит/обновляет чат, пользователя и его членство. Без commit."""
    await session.execute(
        sqlite_insert(Chat)
        .values(id=chat_id, title=chat_title or "")
        .on_conflict_do_update(index_elements=["id"], set_={"title": chat_title or ""})
    )
    await session.execute(
        sqlite_insert(User)
        .values(id=user.id, username=user.username, first_name=user.first_name or "")
        .on_conflict_do_update(
            index_elements=["id"],
            set_={"username": user.username, "first_name": user.first_name or ""},
        )
    )
    member_set = {"left_chat": left}
    await session.execute(
        sqlite_insert(ChatMember)
        .values(chat_id=chat_id, user_id=user.id, left_chat=left)
        .on_conflict_do_update(
            index_elements=["chat_id", "user_id"], set_=member_set
        )
    )


def _collect_users(event: Message) -> list[TgUser]:
    """Все пользователи, раскрытые в одном сообщении (без ботов, без дублей)."""
    found: dict[int, TgUser] = {}

    def add(u: TgUser | None) -> None:
        if u and not u.is_bot:
            found[u.id] = u

    add(event.from_user)
    if event.reply_to_message:
        add(event.reply_to_message.from_user)
    for ent in (event.entities or []):
        if ent.type == "text_mention":
            add(ent.user)
    for u in (event.new_chat_members or []):
        add(u)
    return list(found.values())


class RegistrationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        chat = event.chat
        if chat and chat.type in _GROUP_TYPES:
            users = _collect_users(event)
            if users:
                async with get_session() as session:
                    for u in users:
                        await upsert_member(session, chat.id, chat.title or "", u)
                    await session.commit()
        return await handler(event, data)


class ChatMemberMiddleware(BaseMiddleware):
    """Ловит апдейты chat_member: вступление/выход участника."""

    async def __call__(
        self,
        handler: Callable[[ChatMemberUpdated, dict[str, Any]], Awaitable[Any]],
        event: ChatMemberUpdated,
        data: dict[str, Any],
    ) -> Any:
        chat = event.chat
        member = event.new_chat_member
        if chat and chat.type in _GROUP_TYPES and member and member.user \
                and not member.user.is_bot:
            left = member.status in ("left", "kicked")
            async with get_session() as session:
                await upsert_member(
                    session, chat.id, chat.title or "", member.user, left=left
                )
                await session.commit()
        return await handler(event, data)
