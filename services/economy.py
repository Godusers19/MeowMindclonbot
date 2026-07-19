"""Сервис экономики: баллы, нормы, группы, топ.

Все операции идут через ChatMember (связка chat_id + user_id).
Участник создаётся автоматически при первом сообщении (middleware),
но здесь есть get_or_create на случай выдачи баллов «молчуну» по ID.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database.models import Chat, ChatMember, User
from database.session import get_session

# допустимые группы участников
GROUPS = {"osnova", "neosnovy", "soyuz", "twiny"}

# человекочитаемые названия групп
GROUP_TITLES = {
    "osnova": "Основа",
    "neosnovy": "Не основа",
    "soyuz": "Союз",
    "twiny": "Твины",
}

# сопоставление названия нормы в модели Chat -> группа
GROUP_NORM_FIELD = {
    "osnova": "norm_osnova",
    "neosnovy": "norm_neosnovy",
    "soyuz": "norm_soyuz",
    "twiny": "norm_twiny",
}


async def _ensure_member(session, chat_id: int, user_id: int) -> ChatMember:
    """Возвращает участника, создавая запись при необходимости."""
    member = await session.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id, ChatMember.user_id == user_id
        )
    )
    if member is None:
        # убедимся, что user существует (FK)
        await session.execute(
            sqlite_insert(User)
            .values(id=user_id, first_name="")
            .on_conflict_do_nothing(index_elements=["id"])
        )
        member = ChatMember(chat_id=chat_id, user_id=user_id, points=0)
        session.add(member)
        await session.flush()
    return member


async def add_points(chat_id: int, user_id: int, amount: int) -> int:
    """Изменяет баллы участника на amount (может быть отрицательным).

    Возвращает новый баланс.
    """
    async with get_session() as session:
        member = await _ensure_member(session, chat_id, user_id)
        member.points += amount
        await session.commit()
        return member.points


async def get_points(chat_id: int, user_id: int) -> int:
    async with get_session() as session:
        pts = await session.scalar(
            select(ChatMember.points).where(
                ChatMember.chat_id == chat_id, ChatMember.user_id == user_id
            )
        )
        return pts or 0


async def add_points_bulk(chat_id: int, user_ids: list[int], amount: int) -> int:
    """Выдаёт amount баллов каждому из списка. Возвращает число затронутых."""
    async with get_session() as session:
        for uid in user_ids:
            member = await _ensure_member(session, chat_id, uid)
            member.points += amount
        await session.commit()
        return len(user_ids)


async def get_top(chat_id: int, limit: int = 20) -> list[tuple[int, str, int]]:
    """Топ участников: [(user_id, отображаемое_имя, баллы), ...]."""
    async with get_session() as session:
        rows = await session.execute(
            select(ChatMember.user_id, User.first_name, User.username, ChatMember.points)
            .join(User, User.id == ChatMember.user_id)
            .where(ChatMember.chat_id == chat_id, ChatMember.left_chat == False)  # noqa: E712
            .order_by(ChatMember.points.desc())
            .limit(limit)
        )
        result = []
        for uid, first_name, username, points in rows:
            name = first_name or (f"@{username}" if username else str(uid))
            result.append((uid, name, points))
        return result


async def get_display_name(chat_id: int, user_id: int) -> str:
    """Имя пользователя для отображения (first_name → @username → id)."""
    async with get_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            return str(user_id)
        return user.first_name or (f"@{user.username}" if user.username else str(user_id))


async def get_norm_report(chat_id: int):
    """Отчёт по норме для .обаллы.

    Возвращает (norm, met, not_met, total), где met/not_met — списки
    (user_id, имя, баллы), norm — глобальная норма чата.
    """
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        norm = chat.norm_global if chat else 0

        rows = await session.execute(
            select(ChatMember.user_id, User.first_name, User.username, ChatMember.points)
            .join(User, User.id == ChatMember.user_id)
            .where(ChatMember.chat_id == chat_id, ChatMember.left_chat == False)  # noqa: E712
            .order_by(ChatMember.points.desc())
        )
        met, not_met = [], []
        for uid, first_name, username, points in rows:
            name = first_name or (f"@{username}" if username else str(uid))
            (met if points >= norm and norm > 0 else not_met).append((uid, name, points))
        # если норма не задана — все считаются «выполнившими» (как в оригинале)
        if norm <= 0:
            met = [(uid, n, p) for uid, n, p in
                   sorted(met + not_met, key=lambda r: -r[2])]
            not_met = []
        return norm, met, not_met, len(met) + len(not_met)


async def set_group(chat_id: int, user_id: int, group: str) -> bool:
    """Меняет группу участника. Возвращает False, если группа неверная."""
    if group not in GROUPS:
        return False
    async with get_session() as session:
        member = await _ensure_member(session, chat_id, user_id)
        member.group = group
        await session.commit()
        return True


async def set_prefix(chat_id: int, user_id: int, prefix: str | None) -> None:
    async with get_session() as session:
        member = await _ensure_member(session, chat_id, user_id)
        member.prefix = prefix
        await session.commit()


async def set_norm(chat_id: int, value: int, group: str | None = None) -> None:
    """Устанавливает норму: глобальную (group=None) или для группы."""
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            chat = Chat(id=chat_id)
            session.add(chat)
        if group is None:
            chat.norm_global = value
        else:
            field = GROUP_NORM_FIELD.get(group)
            if field:
                setattr(chat, field, value)
        await session.commit()


async def new_season(chat_id: int) -> int:
    """Обнуляет баллы всех участников чата. Возвращает число обнулённых."""
    async with get_session() as session:
        members = await session.scalars(
            select(ChatMember).where(ChatMember.chat_id == chat_id)
        )
        count = 0
        for m in members:
            m.points = 0
            count += 1
        await session.commit()
        return count


async def set_channel(chat_id: int, channel: str | None) -> None:
    """Привязывает/отвязывает канал с баллами."""
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            chat = Chat(id=chat_id)
            session.add(chat)
        chat.points_channel = channel
        chat.points_message_id = None
        await session.commit()
