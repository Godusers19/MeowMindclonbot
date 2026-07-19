"""SQLAlchemy 2.0 модели данных.

Основная модель прав/баллов — на связку (chat_id, user_id) через ChatMember.
Пользователь регистрируется автоматически при первом сообщении (middleware).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Чаты и пользователи ────────────────────────────────────

class Chat(Base):
    """Группа/чат, где работает бот, и его настройки."""
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram chat_id
    title: Mapped[str] = mapped_column(String(256), default="")

    # Нормы баллов
    norm_global: Mapped[int] = mapped_column(Integer, default=0)
    norm_osnova: Mapped[int] = mapped_column(Integer, default=0)
    norm_neosnovy: Mapped[int] = mapped_column(Integer, default=0)
    norm_soyuz: Mapped[int] = mapped_column(Integer, default=0)
    norm_twiny: Mapped[int] = mapped_column(Integer, default=0)

    # Настройки-переключатели
    only_caps: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_transfer: Mapped[bool] = mapped_column(Boolean, default=False)

    # Привязанный канал с баллами (@username или id)
    points_channel: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # id сообщения топа в канале (чтобы обновлять, а не слать новое)
    points_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    """Глобальный пользователь Telegram."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram user_id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(256), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ChatMember(Base):
    """Участник конкретного чата: баллы, группа, приставка."""
    __tablename__ = "chat_members"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_chat_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)

    points: Mapped[int] = mapped_column(Integer, default=0)
    # группа: osnova / neosnovy / soyuz / twiny
    group: Mapped[str] = mapped_column(String(16), default="neosnovy")
    prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)

    left_chat: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ─── Модерация ──────────────────────────────────────────────

class Punishment(Base):
    """История наказаний: варн/мут/кик/бан."""
    __tablename__ = "punishments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    # тип: warn / mute / kick / ban
    kind: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_by: Mapped[int] = mapped_column(BigInteger)
    # для варнов: активен ли (снятые варны -> active=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # для мутов: до какого времени
    until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ─── Кэпы и права ───────────────────────────────────────────

class Cap(Base):
    """Кэп (расширенный модератор) в чате с флагами прав."""
    __tablename__ = "caps"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_cap"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    can_warn: Mapped[bool] = mapped_column(Boolean, default=True)
    can_mute: Mapped[bool] = mapped_column(Boolean, default=True)
    can_kick: Mapped[bool] = mapped_column(Boolean, default=True)
    can_ban: Mapped[bool] = mapped_column(Boolean, default=True)
    can_points: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ─── Игры и опросы ──────────────────────────────────────────

class Game(Base):
    """Запланированная игра."""
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PollTemplate(Base):
    """Шаблон опроса (для ручной отправки и авто-опросов)."""
    __tablename__ = "poll_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text)  # JSON-список вариантов
    # авто-отправка: cron-подобное расписание (напр. "20:00" ежедневно) или NULL
    schedule: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ─── Интерактивные списки ───────────────────────────────────

class ListTemplate(Base):
    """Шаблон интерактивного списка с плейсхолдерами {user}/{cap}."""
    __tablename__ = "list_templates"
    __table_args__ = (UniqueConstraint("chat_id", "number", name="uq_list"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    number: Mapped[int] = mapped_column(Integer)
    template: Mapped[str] = mapped_column(Text)
    cap_limit: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[int] = mapped_column(BigInteger)


# ─── Магазин ────────────────────────────────────────────────

class ShopItem(Base):
    """Товар в магазине за баллы."""
    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    # тип: auto (бот выполняет) / manual (пишет админу)
    kind: Mapped[str] = mapped_column(String(16))
    price: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # для авто-товаров: действие (напр. "remove_warn")
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ─── Кастомные команды ──────────────────────────────────────

class CustomCommand(Base):
    """Пользовательская команда (+кмнд): текст, медиа, кнопки."""
    __tablename__ = "custom_commands"
    __table_args__ = (UniqueConstraint("chat_id", "trigger", name="uq_cmd"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    trigger: Mapped[str] = mapped_column(String(64))
    # медиа: тип и file_id (если есть)
    media_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    media_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    aliases: Mapped[list["CommandAlias"]] = relationship(
        back_populates="command", cascade="all, delete-orphan"
    )


class CommandAlias(Base):
    """Вариант ответа для кастомной команды (алиас). Первый — основной."""
    __tablename__ = "command_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("custom_commands.id"), index=True
    )
    text: Mapped[str] = mapped_column(Text, default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    command: Mapped["CustomCommand"] = relationship(back_populates="aliases")
