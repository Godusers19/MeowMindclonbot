"""Хендлеры кэпов: +кэп/-кэп, .кэпы, .права (кнопки), .сброскэпов,
   .только_кепы, .передача_баллов.
"""
from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from keyboards.caps import cap_rights_keyboard
from services import caps
from services import economy
from services.caps import CAP_PERMISSIONS
from services.permissions import is_chat_creator, is_owner
from utils.filters import TextCommand
from utils.target import resolve_target

router = Router()


async def _is_boss(bot: Bot, message: Message) -> bool:
    """Только владелец бота или создатель чата управляют кэпами."""
    return (
        await is_owner(message.from_user.id)
        or await is_chat_creator(bot, message.chat.id, message.from_user.id)
    )


def _link(uid: int) -> str:
    return f'<a href="tg://user?id={uid}">пользователь</a>'


# ─── Назначение / снятие ────────────────────────────────────

@router.message(TextCommand("+кэп"))
async def cmd_add_cap(message: Message, bot: Bot) -> None:
    if not await _is_boss(bot, message):
        await message.reply("⛔ Назначать кэпов может только владелец бота или создатель чата.")
        return
    target_id, _ = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель. Ответьте на сообщение или укажите @ник/ID.")
        return
    if await caps.add_cap(message.chat.id, target_id):
        await message.reply(f"👑 {_link(target_id)} назначен кэпом (со всеми правами).")
    else:
        await message.reply("Этот пользователь уже кэп.")


@router.message(TextCommand("-кэп"))
async def cmd_remove_cap(message: Message, bot: Bot) -> None:
    if not await _is_boss(bot, message):
        await message.reply("⛔ Недостаточно прав.")
        return
    target_id, _ = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return
    if await caps.remove_cap(message.chat.id, target_id):
        await message.reply(f"✅ {_link(target_id)} больше не кэп.")
    else:
        await message.reply("Этот пользователь не был кэпом.")


# ─── Список кэпов ───────────────────────────────────────────

@router.message(TextCommand(".кэпы"))
async def cmd_list_caps(message: Message) -> None:
    cap_list = await caps.list_caps(message.chat.id)
    if not cap_list:
        await message.reply("👮‍♂️ В этом чате нет кэпов.")
        return
    lines = ["👮‍♂️ <b>Кэпы этого чата:</b>\n"]
    for cap in cap_list:
        perms = [t for f, t in CAP_PERMISSIONS.items() if getattr(cap, f)]
        perms_str = ", ".join(perms) if perms else "нет прав"
        name = await economy.get_display_name(message.chat.id, cap.user_id)
        safe = html.escape(name)
        link = f'<a href="tg://user?id={cap.user_id}">{safe}</a>'
        lines.append(f"👤 {link}")
        lines.append(f"   Права: {perms_str}")
    await message.reply("\n".join(lines))


# ─── Управление правами (кнопки) ────────────────────────────

@router.message(TextCommand(".права"))
async def cmd_rights(message: Message, bot: Bot) -> None:
    if not await _is_boss(bot, message):
        await message.reply("⛔ Недостаточно прав.")
        return
    target_id, _ = await resolve_target(message)
    if target_id is None:
        await message.reply("Не указана цель.")
        return
    cap = await caps.get_cap(message.chat.id, target_id)
    if cap is None:
        await message.reply("Этот пользователь не кэп. Сначала: +кэп")
        return
    await message.reply(
        f"⚙️ Права кэпа {_link(target_id)}.\n"
        f"Нажимайте, чтобы включить/выключить. Затем «Готово».",
        reply_markup=cap_rights_keyboard(message.chat.id, target_id, cap),
    )


@router.callback_query(F.data.startswith("capperm:"))
async def cb_toggle_perm(callback: CallbackQuery, bot: Bot) -> None:
    _, chat_id, user_id, flag = callback.data.split(":")
    chat_id, user_id = int(chat_id), int(user_id)

    # проверка прав нажимающего
    if not (await is_owner(callback.from_user.id)
            or await is_chat_creator(bot, chat_id, callback.from_user.id)):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    cap = await caps.toggle_permission(chat_id, user_id, flag)
    if cap is None:
        await callback.answer("Кэп не найден.", show_alert=True)
        return
    await callback.message.edit_reply_markup(
        reply_markup=cap_rights_keyboard(chat_id, user_id, cap)
    )
    await callback.answer(f"{CAP_PERMISSIONS[flag]}: {'вкл' if getattr(cap, flag) else 'выкл'}")


@router.callback_query(F.data.startswith("capdone:"))
async def cb_done(callback: CallbackQuery, bot: Bot) -> None:
    _, chat_id, user_id = callback.data.split(":")
    chat_id, user_id = int(chat_id), int(user_id)
    if not (await is_owner(callback.from_user.id)
            or await is_chat_creator(bot, chat_id, callback.from_user.id)):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    cap = await caps.get_cap(chat_id, user_id)
    perms = [t for f, t in CAP_PERMISSIONS.items() if cap and getattr(cap, f)]
    perms_str = ", ".join(perms) if perms else "нет прав"
    await callback.message.edit_text(
        f"✅ Права сохранены для {_link(user_id)}: {perms_str}."
    )
    await callback.answer("Сохранено")


# ─── Сброс кэпов ────────────────────────────────────────────

@router.message(TextCommand(".сброскэпов"))
async def cmd_reset_caps(message: Message, bot: Bot) -> None:
    if not await _is_boss(bot, message):
        await message.reply("⛔ Недостаточно прав.")
        return
    count = await caps.reset_caps(message.chat.id)
    await message.reply(f"🗑 Удалено кэпов: <b>{count}</b>.")


# ─── Режимы ─────────────────────────────────────────────────

@router.message(TextCommand(".только_кепы"))
async def cmd_only_caps(message: Message, bot: Bot) -> None:
    if not await _is_boss(bot, message):
        await message.reply("⛔ Недостаточно прав.")
        return
    enabled = await caps.toggle_only_caps(message.chat.id)
    if enabled:
        await message.reply(
            "🔒 Режим «только кэпы» <b>включён</b>.\n"
            "Обычные TG-админы без статуса кэпа больше не могут "
            "выдавать варны/мут/кик/бан и баллы."
        )
    else:
        await message.reply("🔓 Режим «только кэпы» <b>выключен</b>.")


@router.message(TextCommand(".передача_баллов"))
async def cmd_transfer(message: Message, bot: Bot) -> None:
    if not await _is_boss(bot, message):
        await message.reply("⛔ Недостаточно прав.")
        return
    enabled = await caps.toggle_transfer(message.chat.id)
    state = "включена" if enabled else "выключена"
    await message.reply(f"💸 Передача баллов между участниками <b>{state}</b>.")
