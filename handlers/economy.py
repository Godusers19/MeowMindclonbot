"""Хендлеры экономики: баллы, топ, нормы, группы, приставки, сезон, канал."""
from __future__ import annotations

import html

from aiogram import Bot, Router
from aiogram.types import Message

from services import economy
from services import list_runtime as rt
from services import sync
from services.economy import GROUP_TITLES
from services.permissions import can_do, is_chat_creator, is_owner
from utils.filters import TextCommand
from utils.target import parse_amount, resolve_target

router = Router()


def _mention(uid: int, name: str) -> str:
    safe = html.escape(name)
    return f'<a href="tg://user?id={uid}">{safe}</a>'


def _ball_word(n) -> str:
    """Склонение: 1 балл, 2 балла, 5 баллов (n может быть float)."""
    n_int = int(n)
    if n == n_int:
        n = n_int
    tail = abs(int(n)) % 100
    if 11 <= tail <= 14:
        return "баллов"
    d = tail % 10
    if d == 1:
        return "балл"
    if 2 <= d <= 4:
        return "балла"
    return "баллов"


# ─── Баланс ─────────────────────────────────────────────────

@router.message(TextCommand(".баллы"))
async def cmd_balance(message: Message) -> None:
    # цель — reply/аргумент, иначе сам автор
    target_id, _ = await resolve_target(message)
    uid = target_id or message.from_user.id
    points = await economy.get_points(message.chat.id, uid)
    who = "Ваш баланс" if uid == message.from_user.id else f"Баланс {uid}"
    await message.reply(f"💰 {who}: <b>{points}</b> баллов.")


# ─── Синхронизация участников ───────────────────────────────

@router.message(TextCommand(".синхрон"))
async def cmd_sync(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Синхронизировать могут админы/кэпы.")
        return
    try:
        n = await sync.sync_admins(bot, message.chat.id, message.chat.title or "")
    except Exception as e:  # noqa: BLE001
        await message.reply(f"⚠️ Не удалось синхронизировать: {e}")
        return
    await message.reply(
        f"🔄 Добавлено админов: <b>{n}</b>.\n"
        "<i>Остальные попадут в базу автоматически, как только напишут "
        "или войдут в чат — Bot API не даёт полный список участников.</i>"
    )


# ─── Выдать / забрать баллы ─────────────────────────────────

@router.message(TextCommand("+баллы"))
async def cmd_give(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав для управления баллами.")
        return
    amount, rest = parse_amount((message.text or "").split()[1:])
    if amount is None:
        await message.reply("Использование: +баллы [число] [цель]")
        return
    target_id, _ = await resolve_target_after_amount(message)
    if target_id is None:
        await message.reply("Не указана цель. Ответьте на сообщение или укажите @ник/ID.")
        return
    new_balance = await economy.add_points(message.chat.id, target_id, amount)
    name = await economy.get_display_name(message.chat.id, target_id)
    await message.reply(
        f"📈 {_mention(target_id, name)}: <b>+{amount}</b> {_ball_word(amount)}\n"
        f"📊 Всего: <b>{new_balance}</b> {_ball_word(new_balance)}"
    )


@router.message(TextCommand("-баллы"))
async def cmd_take(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав для управления баллами.")
        return
    amount, rest = parse_amount((message.text or "").split()[1:])
    if amount is None:
        await message.reply("Использование: -баллы [число] [цель]")
        return
    target_id, _ = await resolve_target_after_amount(message)
    if target_id is None:
        await message.reply("Не указана цель. Ответьте на сообщение или укажите @ник/ID.")
        return
    new_balance = await economy.add_points(message.chat.id, target_id, -amount)
    name = await economy.get_display_name(message.chat.id, target_id)
    await message.reply(
        f"📉 {_mention(target_id, name)}: <b>−{amount}</b> {_ball_word(amount)}\n"
        f"📊 Всего: <b>{new_balance}</b> {_ball_word(new_balance)}"
    )


async def resolve_target_after_amount(message: Message):
    """Цель для команд вида '+баллы 5 @user': пропускаем число, потом цель.

    Если reply — цель это автор reply (число всё равно первый аргумент).
    """
    # reply имеет приоритет
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id, []
    # иначе цель — второй аргумент (после числа)
    parts = (message.text or "").split()
    args = parts[1:]
    if len(args) >= 2:
        target = args[1]
        if target.lstrip("-").isdigit():
            return int(target), args[2:]
        if target.startswith("@"):
            from utils.target import _resolve_username
            uid = await _resolve_username(target[1:])
            return uid, args[2:]
    return None, []


# ─── Выдать всем в списке ───────────────────────────────────

@router.message(TextCommand("+с_баллы"))
async def cmd_give_list(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав для управления баллами.")
        return
    if not message.reply_to_message:
        await message.reply("Команда используется ответом на сообщение со списком.")
        return
    amount, _ = parse_amount((message.text or "").split()[1:])
    if amount is None:
        await message.reply("Использование: +с_баллы [число] (ответом на список)")
        return

    active = rt.get(message.chat.id, message.reply_to_message.message_id)
    if active is None:
        await message.reply("Это сообщение не является активным списком.")
        return

    user_ids = [s.user_id for s in active.slots if s.user_id]
    if not user_ids:
        await message.reply("В списке пока никто не занял место.")
        return

    count = await economy.add_points_bulk(message.chat.id, user_ids, amount)
    await message.reply(
        f"✅ Выдано по <b>{amount}</b> баллов участникам списка (<b>{count}</b> чел.)."
    )


# ─── Список по норме ────────────────────────────────────────
@router.message(TextCommand(".обаллы"))
async def cmd_top(message: Message, bot: Bot) -> None:
    norm, met, not_met, total = await economy.get_norm_report(message.chat.id)
    if total == 0:
        await message.reply("📋 <b>Список пользователей:</b>\n\nПока никого нет.")
        return

    lines = ["📋 <b>Список пользователей:</b>\n"]
    lines.append(f"✅ <b>Выполнили норму ({norm}):</b>")
    if met:
        for uid, name, points in met:
            lines.append(f"👤 {_mention(uid, name)} • {points} {_ball_word(points)}")
    else:
        lines.append("(Никого)")

    lines.append("")
    lines.append("❌ <b>Не выполнили норму:</b>")
    if not_met:
        for uid, name, points in not_met:
            lines.append(f"👤 {_mention(uid, name)} • {points} {_ball_word(points)}")
    else:
        lines.append("(Никого)")

    lines.append(f"\nВсего: <b>{total}</b>")
    await message.reply("\n".join(lines))


# ─── Нормы ──────────────────────────────────────────────────

@router.message(TextCommand(".норма"))
async def cmd_norm(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    args = (message.text or "").split()[1:]
    if not args:
        await message.reply("Использование: .норма [число] | .норма основа [число]")
        return

    # .норма основа 100
    group_map = {
        "основа": "osnova",
        "неосновы": "neosnovy",
        "союз": "soyuz",
        "твины": "twiny",
    }
    if args[0].lower() in group_map and len(args) >= 2 and args[1].isdigit():
        group = group_map[args[0].lower()]
        await economy.set_norm(message.chat.id, int(args[1]), group)
        await message.reply(
            f"✅ Норма для «{GROUP_TITLES[group]}»: <b>{args[1]}</b>."
        )
        return

    # .норма 100 (глобальная)
    if args[0].isdigit():
        await economy.set_norm(message.chat.id, int(args[0]))
        await message.reply(f"✅ Глобальная норма: <b>{args[0]}</b>.")
        return

    await message.reply("Неверный формат. Пример: .норма 100")


# ─── Группы участников ──────────────────────────────────────

@router.message(TextCommand(".группа"))
async def cmd_group(message: Message, bot: Bot) -> None:
    group_map = {
        "основа": "osnova",
        "неосновы": "neosnovy",
        "союз": "soyuz",
        "твины": "twiny",
    }
    args = (message.text or "").split()[1:]
    if not args:
        await message.reply("Использование: .группа основа | .группа @user основа")
        return

    # .группа основа (себе)
    if args[0].lower() in group_map and len(args) == 1:
        group = group_map[args[0].lower()]
        await economy.set_group(message.chat.id, message.from_user.id, group)
        await message.reply(f"✅ Ваша группа: «{GROUP_TITLES[group]}».")
        return

    # .группа @user основа (другому — нужны права)
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Смена чужой группы — только для админов/кэпов.")
        return
    target_id, rest = await resolve_target(message)
    # найдём название группы в остатке
    grp_word = next((w for w in rest if w.lower() in group_map), None)
    if target_id is None or grp_word is None:
        await message.reply("Укажите цель и группу. Пример: .группа @user основа")
        return
    group = group_map[grp_word.lower()]
    await economy.set_group(message.chat.id, target_id, group)
    await message.reply(f"✅ Группа участника изменена на «{GROUP_TITLES[group]}».")


# ─── Приставка ──────────────────────────────────────────────

@router.message(TextCommand("+приставка"))
async def cmd_prefix(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    parts = (message.text or "").split(maxsplit=1)
    prefix = parts[1].strip() if len(parts) > 1 else None
    target_id, _ = await resolve_target(message)
    uid = target_id or message.from_user.id
    await economy.set_prefix(message.chat.id, uid, prefix)
    await message.reply(f"✅ Приставка установлена: «{html.escape(prefix or '')}».")


# ─── Новый сезон ────────────────────────────────────────────

@router.message(TextCommand(".новый_сезон"))
async def cmd_new_season(message: Message, bot: Bot) -> None:
    # только владелец бота или создатель чата
    if not (await is_owner(message.from_user.id)
            or await is_chat_creator(bot, message.chat.id, message.from_user.id)):
        await message.reply("⛔ Обнулять сезон может только владелец бота или создатель чата.")
        return
    count = await economy.new_season(message.chat.id)
    await message.reply(f"🔄 Новый сезон! Обнулено баллов у <b>{count}</b> участников.")


# ─── Канал с баллами ────────────────────────────────────────

@router.message(TextCommand("+канал"))
async def cmd_bind_channel(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    args = (message.text or "").split()[1:]
    if not args:
        await message.reply("Использование: +канал @username")
        return
    await economy.set_channel(message.chat.id, args[0])
    await message.reply(f"📡 Канал <b>{html.escape(args[0])}</b> привязан к группе.")


@router.message(TextCommand("-канал"))
async def cmd_unbind_channel(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    await economy.set_channel(message.chat.id, None)
    await message.reply("📡 Канал отвязан от группы.")
