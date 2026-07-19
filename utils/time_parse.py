"""Парсинг длительности мута: 5м / 2ч / 1д / 30с и т.п."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from utils.now import utcnow

# Русские и латинские суффиксы -> секунды
_UNITS = {
    "с": 1, "s": 1,
    "м": 60, "m": 60,
    "ч": 3600, "h": 3600,
    "д": 86400, "d": 86400,
    "н": 604800, "w": 604800,  # неделя
}

_PATTERN = re.compile(r"^(\d+)\s*([a-zа-я]?)$", re.IGNORECASE)


def parse_duration(text: str) -> timedelta | None:
    """Преобразует '5м', '2ч', '1д', '30с' в timedelta.

    Возвращает None, если строка не похожа на длительность
    (тогда вызывающий код трактует мут как «навсегда»).
    """
    if not text:
        return None
    m = _PATTERN.match(text.strip().lower())
    if not m:
        return None
    value, unit = m.groups()
    seconds = int(value) * _UNITS.get(unit or "м", 60)
    if seconds <= 0:
        return None
    return timedelta(seconds=seconds)


def until_from_now(text: str) -> datetime | None:
    """Возвращает момент окончания мута (сейчас + длительность) или None."""
    delta = parse_duration(text)
    if delta is None:
        return None
    return utcnow() + delta


def human_duration(delta: timedelta) -> str:
    """Человекочитаемая длительность: '2 ч 30 мин'."""
    total = int(delta.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    return " ".join(parts) or "0 мин"
