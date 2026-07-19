"""Runtime активных списков: кто какое место занял.

Активный список живёт в памяти и привязан к (chat_id, message_id) сообщения
со списком. Шаблон содержит плейсхолдеры {user} и {cap} — каждый становится
отдельным слотом. Игроки занимают/освобождают слоты кнопками.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# {user} или {cap} — плейсхолдер одного слота
_SLOT_RE = re.compile(r"\{(user|cap)\}")


@dataclass
class Slot:
    kind: str          # "user" или "cap"
    user_id: int | None = None
    user_name: str | None = None


@dataclass
class ActiveList:
    chat_id: int
    number: int
    template: str
    slots: list[Slot] = field(default_factory=list)
    cap_limit: int = 0  # доп. ограничение числа кэп-слотов (0 = как в шаблоне)

    def occupied_caps(self) -> int:
        return sum(1 for s in self.slots if s.kind == "cap" and s.user_id)


# хранилище: (chat_id, message_id) -> ActiveList
_active: dict[tuple[int, int], ActiveList] = {}


def build_active(template: str, chat_id: int, number: int, cap_limit: int) -> ActiveList:
    """Разбирает шаблон в набор слотов."""
    slots = [Slot(kind=m.group(1)) for m in _SLOT_RE.finditer(template)]
    return ActiveList(
        chat_id=chat_id, number=number, template=template,
        slots=slots, cap_limit=cap_limit,
    )


def register(chat_id: int, message_id: int, active: ActiveList) -> None:
    _active[(chat_id, message_id)] = active


def get(chat_id: int, message_id: int) -> ActiveList | None:
    return _active.get((chat_id, message_id))


def drop(chat_id: int, message_id: int) -> None:
    _active.pop((chat_id, message_id), None)


def toggle_slot(
    active: ActiveList, slot_index: int, user_id: int, user_name: str
) -> str:
    """Пытается занять/освободить слот. Возвращает код результата:

      "took"     — занял слот
      "left"     — освободил свой слот
      "occupied" — слот занят другим
      "already"  — пользователь уже в другом слоте (сначала выйдите)
      "cap_full" — лимит кэпов исчерпан
      "bad"      — неверный индекс
    """
    if slot_index < 0 or slot_index >= len(active.slots):
        return "bad"
    slot = active.slots[slot_index]

    # свой слот -> освободить
    if slot.user_id == user_id:
        slot.user_id = None
        slot.user_name = None
        return "left"

    # занят другим
    if slot.user_id is not None:
        return "occupied"

    # пользователь уже занимает другой слот?
    for s in active.slots:
        if s.user_id == user_id:
            return "already"

    # лимит кэпов
    if slot.kind == "cap" and active.cap_limit:
        if active.occupied_caps() >= active.cap_limit:
            return "cap_full"

    slot.user_id = user_id
    slot.user_name = user_name
    return "took"


def render(active: ActiveList) -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает текст списка и клавиатуру слотов.

    В тексте плейсхолдеры заменяются на «— свободно —» или имя занявшего.
    Кнопки: по одной на слот (клик = занять/освободить).
    """
    parts = _SLOT_RE.split(active.template)
    # split с группой возвращает: [text, kind, text, kind, ...]
    out = []
    slot_i = 0
    i = 0
    while i < len(parts):
        out.append(parts[i])  # обычный текст
        if i + 1 < len(parts):
            # parts[i+1] — это 'user'/'cap', соответствует slots[slot_i]
            slot = active.slots[slot_i]
            if slot.user_id:
                out.append(f"<b>{slot.user_name}</b>")
            else:
                label = "капитан" if slot.kind == "cap" else "игрок"
                out.append(f"— {label} —")
            slot_i += 1
        i += 2

    text = "".join(out)

    # клавиатура: кнопка на каждый слот
    rows = []
    row = []
    for idx, slot in enumerate(active.slots):
        mark = "🔴" if slot.user_id else ("🟡" if slot.kind == "cap" else "🟢")
        title = "Кэп" if slot.kind == "cap" else "Игрок"
        row.append(InlineKeyboardButton(
            text=f"{mark} {title} {idx + 1}",
            callback_data=f"listslot:{active.chat_id}:{idx}",
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return text, InlineKeyboardMarkup(inline_keyboard=rows)
