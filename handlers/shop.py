"""Хендлеры магазина: .магазин, +товар, -товар, покупка (callback)."""
from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from keyboards.shop import shop_keyboard
from services import economy, shop
from services import moderation as mod
from services.permissions import can_do
from utils.filters import TextCommand

router = Router()


# ─── Витрина ────────────────────────────────────────────────

@router.message(TextCommand(".магазин"))
async def cmd_shop(message: Message) -> None:
    items = await shop.list_items(message.chat.id)
    if not items:
        await message.reply(
            "💎 <b>Магазин пуст</b>\n\n"
            "Добавить товар (только админ):\n"
            "<code>+товар авто 15 Снять варн | Описание</code>\n"
            "<code>+товар ручной 20 5 лапок | Описание</code>"
        )
        return
    lines = ["🛒 <b>Магазин</b>\n"]
    for it in items:
        tag = "🤖" if it.kind == "auto" else "🙋"
        desc = f"\n   <i>{html.escape(it.description)}</i>" if it.description else ""
        lines.append(f"{tag} <b>{html.escape(it.name)}</b> — {it.price} б. (ID {it.id}){desc}")
    await message.answer("\n".join(lines), reply_markup=shop_keyboard(items))


# ─── Добавление товара ──────────────────────────────────────

@router.message(TextCommand("+товар"))
async def cmd_add_item(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Управлять магазином могут только админы/кэпы.")
        return

    # формат: +товар <авто|ручной> <цена> <название> | <описание>
    text = (message.text or "").split(maxsplit=1)
    if len(text) < 2:
        await message.reply(
            "Использование:\n"
            ".+товар авто [цена] [название] | [описание]\n"
            ".+товар ручной [цена] [название] | [описание]"
        )
        return

    body = text[1]
    parts = body.split("|", 1)
    head = parts[0].split()
    description = parts[1].strip() if len(parts) > 1 else None

    if len(head) < 3:
        await message.reply("Нужно: тип, цена и название. Пример: +товар авто 15 Снять варн | ...")
        return

    kind_word = head[0].lower()
    if kind_word not in ("авто", "ручной"):
        await message.reply("Тип должен быть «авто» или «ручной».")
        return
    kind = "auto" if kind_word == "авто" else "manual"

    if not head[1].isdigit():
        await message.reply("Цена должна быть числом.")
        return
    price = int(head[1])
    name = " ".join(head[2:])

    # для авто-товаров пытаемся угадать действие по названию
    action = None
    if kind == "auto":
        low = name.lower()
        if "варн" in low:
            action = "remove_warn"

    item = await shop.add_item(
        message.chat.id, kind, price, name, description, action
    )
    tag = "🤖 авто" if kind == "auto" else "🙋 ручной"
    await message.reply(
        f"✅ Товар добавлен: <b>{html.escape(name)}</b> ({tag}) — {price} б. ID {item.id}"
    )


# ─── Удаление товара ────────────────────────────────────────

@router.message(TextCommand("-товар"))
async def cmd_remove_item(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Использование: -товар [ID или название]")
        return
    if await shop.remove_item(message.chat.id, args[1].strip()):
        await message.reply("🗑 Товар удалён.")
    else:
        await message.reply("Товар не найден.")


# ─── Покупка ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, bot: Bot) -> None:
    _, chat_id, item_id = callback.data.split(":")
    chat_id, item_id = int(chat_id), int(item_id)
    buyer = callback.from_user

    item = await shop.get_item(chat_id, item_id)
    if item is None:
        await callback.answer("Товар больше недоступен.", show_alert=True)
        return

    balance = await economy.get_points(chat_id, buyer.id)
    if balance < item.price:
        await callback.answer(
            f"Недостаточно баллов: нужно {item.price}, у вас {balance}.",
            show_alert=True,
        )
        return

    # списываем баллы
    await economy.add_points(chat_id, buyer.id, -item.price)
    name = buyer.first_name or "Пользователь"
    mention = f'<a href="tg://user?id={buyer.id}">{html.escape(name)}</a>'

    if item.kind == "auto":
        result = await _run_auto_action(chat_id, buyer.id, item)
        await callback.answer("Покупка выполнена ✅", show_alert=False)
        await callback.message.answer(
            f"🤖 {mention} купил «{html.escape(item.name)}». {result}"
        )
    else:
        await callback.answer("Покупка оформлена ✅", show_alert=False)
        await callback.message.answer(
            f"🙋 {mention} купил «{html.escape(item.name)}» за {item.price} б.\n"
            f"Админ, выполните вручную: {html.escape(item.description or item.name)}"
        )


async def _run_auto_action(chat_id: int, user_id: int, item) -> str:
    """Выполняет авто-действие товара."""
    if item.action == "remove_warn":
        if await mod.remove_last_warn(chat_id, user_id):
            count = await mod.count_active_warns(chat_id, user_id)
            return f"Снят 1 варн (осталось {count})."
        return "Активных варнов не было."
    return "Действие выполнено."
