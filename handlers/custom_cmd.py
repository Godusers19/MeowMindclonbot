"""Хендлеры кастомных команд: +кмнд, +алиас, .алиасы, -алиас и вызов .триггер.

Роутер вызова .триггер подключается ПОСЛЕДНИМ — чтобы не перехватывать
встроенные команды. Он проверяет наличие триггера в БД.
"""
from __future__ import annotations

import random

from aiogram import Bot, F, Router
from aiogram.types import Message

from services import custom_cmd as cc
from services.permissions import can_do
from utils.custom_parse import apply_substitutions, extract_buttons
from utils.filters import TextCommand

router = Router()

# отдельный роутер для динамического вызова .триггер —
# подключается ПОСЛЕДНИМ, чтобы не перехватывать встроенные команды
dynamic_router = Router()


def _media_of(message: Message) -> tuple[str | None, str | None]:
    """Определяет медиа сообщения: (тип, file_id)."""
    if message.photo:
        return "photo", message.photo[-1].file_id
    if message.video:
        return "video", message.video.file_id
    if message.animation:
        return "animation", message.animation.file_id
    return None, None


# ─── Создание команды ───────────────────────────────────────

@router.message(TextCommand("+кмнд"))
async def cmd_create(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Создавать команды могут админы/кэпы.")
        return

    raw = message.text or message.caption or ""
    lines = raw.split("\n", 1)
    header = lines[0].split()
    if len(header) < 2:
        await message.reply("Использование: +кмнд [триггер]\n[текст ответа]")
        return
    trigger = header[1].lower().lstrip(".")
    body = lines[1].strip() if len(lines) > 1 else ""

    media_type, media_id = _media_of(message)
    if not body and not media_type:
        await message.reply("Добавьте текст ответа или прикрепите медиа.")
        return

    ok = await cc.create_command(message.chat.id, trigger, body, media_type, media_id)
    if ok:
        await message.reply(
            f"✅ Команда <code>.{trigger}</code> создана. Вызов: <code>.{trigger}</code>"
        )
    else:
        await message.reply(
            f"Команда «{trigger}» уже существует. Добавьте вариант через +алиас."
        )


# ─── Алиасы ─────────────────────────────────────────────────

@router.message(TextCommand("+алиас"))
async def cmd_add_alias(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    raw = message.text or ""
    lines = raw.split("\n", 1)
    header = lines[0].split()
    if len(header) < 2:
        await message.reply("Использование: +алиас [триггер]\n[вариант ответа]")
        return
    trigger = header[1].lower().lstrip(".")
    body = lines[1].strip() if len(lines) > 1 else ""
    if not body:
        await message.reply("Добавьте текст варианта со следующей строки.")
        return
    if await cc.add_alias(message.chat.id, trigger, body):
        await message.reply(f"✅ Вариант добавлен к <code>.{trigger}</code>.")
    else:
        await message.reply(f"Команды «{trigger}» нет. Сначала создайте её через +кмнд.")


@router.message(TextCommand(".алиасы"))
async def cmd_list_aliases(message: Message) -> None:
    args = (message.text or "").split()
    if len(args) < 2:
        await message.reply("Использование: .алиасы [триггер]")
        return
    trigger = args[1].lower().lstrip(".")
    aliases = await cc.list_aliases(message.chat.id, trigger)
    if not aliases:
        await message.reply(f"Команды «{trigger}» нет или у неё нет вариантов.")
        return
    lines = [f"📄 Варианты <code>.{trigger}</code>:\n"]
    for i, a in enumerate(aliases, 1):
        tag = " (основной)" if a.is_primary else ""
        preview = (a.text[:40] + "…") if len(a.text) > 40 else a.text
        lines.append(f"{i}.{tag} {preview}")
    await message.reply("\n".join(lines))


@router.message(TextCommand("-алиас"))
async def cmd_del_alias(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    args = (message.text or "").split()
    if len(args) < 3 or not args[2].isdigit():
        await message.reply("Использование: -алиас [триггер] [номер]")
        return
    trigger = args[1].lower().lstrip(".")
    number = int(args[2])
    result = await cc.delete_alias(message.chat.id, trigger, number)
    msgs = {
        "ok": "✅ Вариант удалён.",
        "primary": "Основной вариант (1) удалить нельзя — удалите команду целиком.",
        "not_found": "Команда не найдена.",
        "bad_number": "Нет варианта с таким номером.",
    }
    await message.reply(msgs.get(result, "Ошибка."))


# ─── Удаление команды ───────────────────────────────────────

@router.message(TextCommand("-кмнд"))
async def cmd_delete(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    args = (message.text or "").split()
    if len(args) < 2:
        await message.reply("Использование: -кмнд [триггер]")
        return
    trigger = args[1].lower().lstrip(".")
    if await cc.delete_command(message.chat.id, trigger):
        await message.reply(f"🗑 Команда «{trigger}» удалена.")
    else:
        await message.reply("Команда не найдена.")


# ─── Вызов .триггер (динамический, последним) ───────────────

@dynamic_router.message(F.text.startswith(".") | F.caption.startswith("."))
async def handle_dynamic(message: Message) -> None:
    """Ловит любое сообщение вида '.слово' и ищет кастомную команду."""
    text = message.text or message.caption
    if not text or not text.startswith("."):
        return
    trigger = text.split()[0][1:].lower()
    if not trigger:
        return

    cmd = await cc.get_command(message.chat.id, trigger)
    if cmd is None or not cmd.aliases:
        return

    # случайный вариант
    variant = random.choice(cmd.aliases)
    target = message.reply_to_message.from_user if message.reply_to_message else None
    body = apply_substitutions(variant.text, target, message.from_user)
    clean, kb = extract_buttons(body)

    if cmd.media_type == "photo":
        await message.answer_photo(cmd.media_id, caption=clean or None, reply_markup=kb)
    elif cmd.media_type == "video":
        await message.answer_video(cmd.media_id, caption=clean or None, reply_markup=kb)
    elif cmd.media_type == "animation":
        await message.answer_animation(cmd.media_id, caption=clean or None, reply_markup=kb)
    else:
        await message.answer(clean or "…", reply_markup=kb)
