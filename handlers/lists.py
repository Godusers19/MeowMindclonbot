"""Хендлеры интерактивных списков.

  +список [номер]        — создать шаблон (текст с новой строки или reply)
  .список [номер]        — вызвать список (шаблон удаляется после вызова)
  .список [номер] -cap N — вызвать и задать лимит кэпов
  -список [номер]        — удалить шаблон
  .лсписок               — показать номера своих списков
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from services import list_runtime as rt
from services import lists
from utils.filters import TextCommand

router = Router()


def _parse_number(args: list[str]) -> int | None:
    if args and args[0].isdigit():
        return int(args[0])
    return None


# ─── Создание шаблона ───────────────────────────────────────

@router.message(TextCommand("+список"))
async def cmd_create(message: Message) -> None:
    text = message.text or ""
    lines = text.split("\n", 1)
    header = lines[0].split()
    number = _parse_number(header[1:])
    if number is None:
        await message.reply("Использование: +список [номер]\n[текст с {user}/{cap}]")
        return

    # тело шаблона: либо со 2-й строки, либо из reply
    body = lines[1] if len(lines) > 1 else None
    if not body and message.reply_to_message:
        body = message.reply_to_message.text or message.reply_to_message.caption
    if not body:
        await message.reply(
            "Добавьте тело списка — с новой строки после команды или ответом на сообщение.\n"
            "Плейсхолдеры: {user} — место игрока, {cap} — место капитана."
        )
        return

    if "{user}" not in body and "{cap}" not in body:
        await message.reply("В шаблоне нет ни одного {user} или {cap}.")
        return

    await lists.save_template(message.chat.id, number, body, message.from_user.id)
    slots = body.count("{user}") + body.count("{cap}")
    await message.reply(
        f"✅ Список <b>№{number}</b> сохранён. Слотов: <b>{slots}</b>.\n"
        f"Вызов: <code>.список {number}</code>"
    )


# ─── Вызов списка ───────────────────────────────────────────

@router.message(TextCommand(".список"))
async def cmd_call(message: Message) -> None:
    args = (message.text or "").split()[1:]
    number = _parse_number(args)
    if number is None:
        await message.reply("Использование: .список [номер] [-cap N]")
        return

    tpl = await lists.get_template(message.chat.id, number)
    if tpl is None:
        await message.reply(f"Список №{number} не найден.")
        return

    # опциональный -cap N
    cap_limit = tpl.cap_limit
    if "-cap" in args:
        i = args.index("-cap")
        if i + 1 < len(args) and args[i + 1].isdigit():
            cap_limit = int(args[i + 1])

    active = rt.build_active(tpl.template, message.chat.id, number, cap_limit)
    text, kb = rt.render(active)
    sent = await message.answer(
        f"📋 <b>Список №{number}</b>\n\n{text}", reply_markup=kb
    )
    rt.register(message.chat.id, sent.message_id, active)

    # «он будет очищен» — удаляем шаблон после вызова
    await lists.delete_template(message.chat.id, number)


# ─── Клик по слоту ──────────────────────────────────────────

@router.callback_query(F.data.startswith("listslot:"))
async def cb_slot(callback: CallbackQuery) -> None:
    _, chat_id, idx = callback.data.split(":")
    chat_id, idx = int(chat_id), int(idx)
    message_id = callback.message.message_id

    active = rt.get(chat_id, message_id)
    if active is None:
        await callback.answer("Этот список больше не активен.", show_alert=True)
        return

    name = callback.from_user.first_name or "Игрок"
    result = rt.toggle_slot(active, idx, callback.from_user.id, name)

    messages = {
        "took": "Вы заняли место ✅",
        "left": "Вы освободили место",
        "occupied": "Место уже занято другим.",
        "already": "Вы уже в списке. Сначала выйдите со своего места.",
        "cap_full": "Лимит капитанов исчерпан.",
        "bad": "Ошибка слота.",
    }
    await callback.answer(messages.get(result, ""))

    if result in ("took", "left"):
        text, kb = rt.render(active)
        await callback.message.edit_text(
            f"📋 <b>Список №{active.number}</b>\n\n{text}", reply_markup=kb
        )


# ─── Удаление / список номеров ──────────────────────────────

@router.message(TextCommand("-список"))
async def cmd_delete(message: Message) -> None:
    args = (message.text or "").split()[1:]
    number = _parse_number(args)
    if number is None:
        await message.reply("Использование: -список [номер]")
        return
    if await lists.delete_template(message.chat.id, number):
        await message.reply(f"🗑 Список №{number} удалён.")
    else:
        await message.reply(f"Список №{number} не найден.")


@router.message(TextCommand(".лсписок"))
async def cmd_list_all(message: Message) -> None:
    numbers = await lists.list_numbers(message.chat.id)
    if not numbers:
        await message.reply("Сохранённых списков нет.")
        return
    nums = ", ".join(f"№{n}" for n in numbers)
    await message.reply(f"📑 Ваши списки: {nums}")
