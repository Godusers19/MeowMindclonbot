"""Хендлеры модерации: варн/сварн, мут/размут, кик, бан/разбан, история.

Цель указывается reply / @ник / ID. Telegram-действия идут через Bot API.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Router
from aiogram.types import ChatPermissions, Message

from services import moderation as mod
from services.moderation import WARN_LIMIT
from services.permissions import can_do
from utils.now import utcnow
from utils.filters import TextCommand
from utils.target import resolve_target
from utils.time_parse import parse_duration, until_from_now, human_duration

router = Router()

MUTED_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
)

UNMUTED_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)


def _tail_reason(args: list[str], skip: int = 0) -> str | None:
    """Собирает причину из хвоста аргументов, пропуская skip первых слов."""
    rest = args[skip:]
    return " ".join(rest).strip() or None


# ─── Варн ───────────────────────────────────────────────────

@router.message(TextCommand(".варн"))
async def cmd_warn(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "warn"):
        await message.reply("⛔ Недостаточно прав для варна.")
        return
    target_id, rest = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель. Ответьте на сообщение или укажите @ник/ID.")
        return
    reason = _tail_reason(rest)
    count = await mod.add_warn(message.chat.id, target_id, message.from_user.id, reason)

    if count >= WARN_LIMIT:
        # авто-бан
        try:
            await bot.ban_chat_member(message.chat.id, target_id)
        except Exception as e:  # noqa: BLE001
            await message.reply(f"⚠️ 3 варна, но не удалось забанить: {e}")
            return
        await mod.clear_active_warns(message.chat.id, target_id)
        await mod.add_punishment(
            message.chat.id, target_id, "ban", message.from_user.id, "авто-бан (3 варна)"
        )
        await message.reply(
            f"🔨 {_link(target_id)} получил <b>{count}/{WARN_LIMIT}</b> варнов "
            f"и был <b>забанен</b> автоматически."
        )
    else:
        r = f"\nПричина: {html.escape(reason)}" if reason else ""
        await message.reply(
            f"⚠️ {_link(target_id)} получил варн <b>{count}/{WARN_LIMIT}</b>.{r}"
        )


@router.message(TextCommand(".сварн"))
async def cmd_unwarn(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "warn"):
        await message.reply("⛔ Недостаточно прав.")
        return
    target_id, _ = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return
    if await mod.remove_last_warn(message.chat.id, target_id):
        count = await mod.count_active_warns(message.chat.id, target_id)
        await message.reply(f"✅ Варн снят. Сейчас: <b>{count}/{WARN_LIMIT}</b>.")
    else:
        await message.reply("У пользователя нет активных варнов.")


# ─── Мут / размут ───────────────────────────────────────────

@router.message(TextCommand(".мут"))
async def cmd_mute(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "mute"):
        await message.reply("⛔ Недостаточно прав для мута.")
        return
    target_id, rest = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return

    # первый аргумент после цели может быть временем (5м/2ч/1д)
    until: datetime | None = None
    skip = 0
    if rest and parse_duration(rest[0]) is not None:
        until = until_from_now(rest[0])
        skip = 1
    reason = _tail_reason(rest, skip)

    try:
        await bot.restrict_chat_member(
            message.chat.id,
            target_id,
            permissions=MUTED_PERMS,
            # Telegram считает until по UTC: naive-дату API трактует
            # по локальному времени сервера и мут «уезжает» в прошлое →
            # ставится навсегда. Передаём aware-UTC, чтобы срок был точным.
            until_date=until.replace(tzinfo=timezone.utc) if until else None,
        )
    except Exception as e:  # noqa: BLE001
        await message.reply(f"⚠️ Не удалось замутить: {e}")
        return

    await mod.add_punishment(
        message.chat.id, target_id, "mute", message.from_user.id, reason, until
    )
    if until:
        delta = until - utcnow()
        dur = human_duration(delta)
        await message.reply(f"🔇 {_link(target_id)} замучен на <b>{dur}</b>.")
    else:
        await message.reply(f"🔇 {_link(target_id)} замучен <b>навсегда</b>.")


@router.message(TextCommand(".размут"))
async def cmd_unmute(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "mute"):
        await message.reply("⛔ Недостаточно прав.")
        return
    target_id, _ = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return
    try:
        await bot.restrict_chat_member(
            message.chat.id, target_id, permissions=UNMUTED_PERMS
        )
    except Exception as e:  # noqa: BLE001
        await message.reply(f"⚠️ Не удалось размутить: {e}")
        return
    await message.reply(f"🔊 {_link(target_id)} размучен.")


# ─── Кик ────────────────────────────────────────────────────

@router.message(TextCommand(".кик"))
async def cmd_kick(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "kick"):
        await message.reply("⛔ Недостаточно прав для кика.")
        return
    target_id, rest = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return
    reason = _tail_reason(rest)
    try:
        # кик = бан + разбан (иначе пользователь остаётся в бане)
        await bot.ban_chat_member(message.chat.id, target_id)
        await bot.unban_chat_member(message.chat.id, target_id)
    except Exception as e:  # noqa: BLE001
        await message.reply(f"⚠️ Не удалось кикнуть: {e}")
        return
    await mod.add_punishment(
        message.chat.id, target_id, "kick", message.from_user.id, reason
    )
    r = f"\nПричина: {html.escape(reason)}" if reason else ""
    await message.reply(f"👢 {_link(target_id)} кикнут из чата.{r}")


# ─── Бан / разбан ───────────────────────────────────────────

@router.message(TextCommand(".бан"))
async def cmd_ban(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "ban"):
        await message.reply("⛔ Недостаточно прав для бана.")
        return
    target_id, rest = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return
    reason = _tail_reason(rest)
    try:
        await bot.ban_chat_member(message.chat.id, target_id)
    except Exception as e:  # noqa: BLE001
        await message.reply(f"⚠️ Не удалось забанить: {e}")
        return
    await mod.add_punishment(
        message.chat.id, target_id, "ban", message.from_user.id, reason
    )
    r = f"\nПричина: {html.escape(reason)}" if reason else ""
    await message.reply(f"🔨 {_link(target_id)} забанен.{r}")


@router.message(TextCommand(".разбан"))
async def cmd_unban(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "ban"):
        await message.reply("⛔ Недостаточно прав.")
        return
    target_id, _ = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return
    try:
        await bot.unban_chat_member(message.chat.id, target_id, only_if_banned=True)
    except Exception as e:  # noqa: BLE001
        await message.reply(f"⚠️ Не удалось разбанить: {e}")
        return
    await message.reply(f"✅ {_link(target_id)} разбанен.")


# ─── История ────────────────────────────────────────────────

@router.message(TextCommand(".история"))
async def cmd_history(message: Message, bot: Bot) -> None:
    target_id, _ = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return
    history = await mod.get_history(message.chat.id, target_id)
    if not history:
        await message.reply("История пуста — наказаний не было.")
        return

    icons = {"warn": "⚠️", "mute": "🔇", "kick": "👢", "ban": "🔨"}
    lines = [f"📋 <b>История наказаний</b> {_link(target_id)}:\n"]
    for p in history[:20]:
        icon = icons.get(p.kind, "•")
        date = p.created_at.strftime("%d.%m.%Y %H:%M")
        reason = f" — {html.escape(p.reason)}" if p.reason else ""
        status = "" if p.active else " (снято)"
        lines.append(f"{icon} {date}{reason}{status}")
    await message.reply("\n".join(lines))


# ─── helpers ────────────────────────────────────────────────

def _link(uid: int) -> str:
    return f'<a href="tg://user?id={uid}">пользователь</a>'
