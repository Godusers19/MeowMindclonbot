"""Меню помощи .помощь с категориями (inline-кнопки)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from utils.filters import TextCommand

router = Router()

MAIN_TEXT = (
    "📖 <b>Главное меню помощи</b>\n\n"
    "Выберите категорию:\n\n"
    "💰 Экономика — баллы и нормы.\n"
    "🔨 Модерация — варны, мут, бан.\n"
    "👑 Кэпы — модераторы и права.\n"
    "📝 Списки — интерактивные наборы.\n"
    "🛒 Магазин — покупки за баллы.\n"
    "🎮 Игры и опросы — расписание.\n"
    "🛠 Кастомные команды — свои команды."
)

SECTIONS = {
    "economy": (
        "💰 <b>Команды экономики:</b>\n\n"
        "• <code>.баллы</code> — ваш баланс.\n"
        "• <code>+баллы [число] [цель]</code> — выдать баллы.\n"
        "• <code>-баллы [число] [цель]</code> — забрать баллы.\n"
        "• <code>+с_баллы [число]</code> — (ответом на список) выдать всем.\n"
        "• <code>.обаллы</code> — топ пользователей.\n"
        "• <code>.норма [число]</code> — глобальный порог.\n"
        "• <code>.норма основа/неосновы/союз/твины [число]</code>.\n"
        "• <code>+приставка [текст]</code> — префикс для учёта.\n"
        "• <code>.новый_сезон</code> — обнулить все баллы.\n"
        "• <code>.группа основа</code> — сменить свою группу.\n"
        "• <code>.группа @user основа</code> — сменить чужую.\n"
        "• <code>+канал @username</code> / <code>-канал</code> — канал с баллами."
    ),
    "moderation": (
        "🔨 <b>Модерация:</b>\n\n"
        "Цель: ответом, по ID или @нику.\n\n"
        "• <code>.варн [цель] [причина]</code> — варн (3 = авто-бан).\n"
        "• <code>.сварн [цель]</code> — снять варн.\n"
        "• <code>.мут [цель] [5м|2ч|1д] [причина]</code> — мут.\n"
        "• <code>.размут [цель]</code> — снять мут.\n"
        "• <code>.кик [цель] [причина]</code> — кик.\n"
        "• <code>.бан [цель] [причина]</code> — бан.\n"
        "• <code>.разбан [цель]</code> — разбан.\n"
        "• <code>.история [цель]</code> — история наказаний."
    ),
    "caps": (
        "👑 <b>Кэпы и права:</b>\n\n"
        "• <code>+кэп [цель]</code> — назначить кэпа.\n"
        "• <code>-кэп [цель]</code> — снять кэпа.\n"
        "• <code>.кэпы</code> — список кэпов.\n"
        "• <code>.права [цель]</code> — управление правами (кнопки).\n"
        "• <code>.сброскэпов</code> — удалить всех кэпов.\n\n"
        "⚙️ <b>Настройки:</b>\n"
        "• <code>.только_кепы</code> — доступ к модерации только у кэпов.\n"
        "• <code>.передача_баллов</code> — вкл/выкл передачу баллов."
    ),
    "lists": (
        "📝 <b>Интерактивные списки:</b>\n\n"
        "• <code>+список [номер]</code> — создать шаблон (текст с новой строки или ответом).\n"
        "• <code>.список [номер]</code> — вызвать (очищается после).\n"
        "• <code>.список [номер] -cap [число]</code> — с лимитом кэпов.\n"
        "• <code>-список [номер]</code> — удалить.\n"
        "• <code>.лсписок</code> — все номера.\n\n"
        "Плейсхолдеры: <code>{user}</code> — игрок, <code>{cap}</code> — капитан."
    ),
    "shop": (
        "🛒 <b>Магазин:</b>\n\n"
        "• <code>.магазин</code> — открыть (с кнопками).\n\n"
        "Управление (админы):\n"
        "• <code>+товар авто [цена] [название] | [описание]</code>\n"
        "• <code>+товар ручной [цена] [название] | [описание]</code>\n"
        "• <code>-товар [ID или название]</code> — удалить.\n\n"
        "Пример:\n<code>.+товар авто 15 Снять варн | Снимает 1 варн</code>"
    ),
    "games": (
        "🎮 <b>Игры и опросы:</b>\n\n"
        "• <code>+игра [ДД.ММ] [ЧЧ:ММ] [описание]</code> — добавить игру.\n"
        "• <code>.расп</code> — расписание.\n"
        "• <code>.отменить [ДД.ММ] [ЧЧ:ММ]</code> — удалить игру.\n"
        "• <code>.опрос [имя_шаблона]</code> — отправить опрос."
    ),
    "custom": (
        "🛠 <b>Кастомные команды:</b>\n\n"
        "1. <code>+кмнд [триггер]</code>\n<code>[текст ответа]</code>\n\n"
        "2. Кнопки: <code>{[Текст - https://ссылка]}</code>\n"
        "3. Подстановки: <code>{name}</code>, <code>{mention}</code>, <code>{sender_name}</code>.\n"
        "4. Медиа: отправьте +кмнд вместе с фото/видео/гиф.\n\n"
        "Алиасы (несколько ответов):\n"
        "• <code>+алиас [триггер]</code>\n<code>[вариант]</code>\n"
        "• <code>.алиасы [триггер]</code> — список вариантов.\n"
        "• <code>-алиас [триггер] [номер]</code> — удалить вариант."
    ),
}

BUTTONS = [
    ("💰 Экономика", "economy"),
    ("🔨 Модерация", "moderation"),
    ("👑 Кэпы", "caps"),
    ("📝 Списки", "lists"),
    ("🛒 Магазин", "shop"),
    ("🎮 Игры", "games"),
    ("🛠 Команды", "custom"),
]


def _main_keyboard() -> InlineKeyboardMarkup:
    rows, row = [], []
    for title, key in BUTTONS:
        row.append(InlineKeyboardButton(text=title, callback_data=f"help:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Назад", callback_data="help:main")
    ]])


@router.message(TextCommand(".помощь"))
async def cmd_help(message: Message) -> None:
    await message.answer(MAIN_TEXT, reply_markup=_main_keyboard())


@router.callback_query(F.data.startswith("help:"))
async def cb_help(callback: CallbackQuery) -> None:
    key = callback.data.split(":", 1)[1]
    if key == "main":
        await callback.message.edit_text(MAIN_TEXT, reply_markup=_main_keyboard())
    elif key in SECTIONS:
        await callback.message.edit_text(SECTIONS[key], reply_markup=_back_keyboard())
    await callback.answer()
