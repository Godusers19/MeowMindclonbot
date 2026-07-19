"""Хендлеры игр и опросов.

  +игра [ДД.ММ] [ЧЧ:ММ] [описание]  — добавить игру + напоминание
  .расп                             — расписание
  .отменить [ДД.ММ] [ЧЧ:ММ]         — удалить игру
  .опрос [имя]                      — отправить опрос по шаблону
  (шаблоны опросов создаются через веб-панель или отдельной командой)
"""
from __future__ import annotations

import html

from aiogram import Bot, Router
from aiogram.types import Message

from services import games
from services.permissions import can_do
from services.scheduler import scheduler
from utils.datetime_parse import parse_game_datetime
from utils.filters import TextCommand

router = Router()

# бот нужен планировщику для авто-опросов
_bot: Bot | None = None


def set_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


# ─── Игры ───────────────────────────────────────────────────

@router.message(TextCommand("+игра"))
async def cmd_add_game(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Планировать игры могут админы/кэпы.")
        return
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3:
        await message.reply("Использование: +игра [ДД.ММ] [ЧЧ:ММ] [описание]")
        return
    dt = parse_game_datetime(parts[1], parts[2])
    if dt is None:
        await message.reply("Неверная дата/время. Пример: +игра 25.12 20:30 Каток")
        return
    description = parts[3] if len(parts) > 3 else "Игра"

    game = await games.add_game(message.chat.id, dt, description)
    await message.reply(
        f"🎮 Игра запланирована на <b>{dt.strftime('%d.%m %H:%M')}</b>\n"
        f"{html.escape(description)}"
    )


@router.message(TextCommand(".расп"))
async def cmd_schedule(message: Message) -> None:
    upcoming = await games.list_games(message.chat.id)
    if not upcoming:
        await message.reply("📅 Расписание пусто.")
        return

    # группируем игры по дате
    by_day: dict[str, list] = {}
    for g in upcoming:
        day = g.starts_at.strftime("%d.%m")
        by_day.setdefault(day, []).append(g)

    blocks = ["📅 <b>Расписание игр:</b>\n"]
    for day, games_of_day in by_day.items():
        block = [f"╔════{day}════╗\n"]
        for g in games_of_day:
            block.append(f"▫️ {g.starts_at.strftime('%H:%M')}")
            block.append(html.escape(g.description))
            block.append("")  # пустая строка-разделитель
        block.append("╚══════════╝")
        blocks.append("\n".join(block))

    await message.reply("\n\n".join(blocks))


@router.message(TextCommand(".отменить"))
async def cmd_cancel(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.reply("Использование: .отменить [ДД.ММ] [ЧЧ:ММ]")
        return
    dt = parse_game_datetime(parts[1], parts[2])
    if dt is None:
        await message.reply("Неверная дата/время.")
        return
    if await games.cancel_game(message.chat.id, dt):
        try:
            scheduler.remove_job(f"game_{dt.timestamp()}")
        except Exception:  # noqa: BLE001
            pass
        await message.reply(f"❌ Игра на {dt.strftime('%d.%m %H:%M')} отменена.")
    else:
        await message.reply("Игра на это время не найдена.")


# ─── Опросы ─────────────────────────────────────────────────

@router.message(TextCommand(".опрос"))
async def cmd_poll(message: Message, bot: Bot) -> None:
    if not await can_do(bot, message, "points"):
        await message.reply("⛔ Недостаточно прав.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        polls = await games.list_polls(message.chat.id)
        hint = ("\nШаблоны: " + ", ".join(polls)) if polls else ""
        await message.reply(f"Использование: .опрос [имя_шаблона]{hint}")
        return
    name = parts[1].strip()
    poll = await games.get_poll(message.chat.id, name)
    if poll is None:
        await message.reply(f"Шаблон опроса «{name}» не найден.")
        return
    question, options = poll
    await bot.send_poll(
        message.chat.id, question=question, options=options, is_anonymous=False
    )
