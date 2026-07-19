"""Парсинг даты и времени игр: 'ДД.ММ' 'ЧЧ:ММ'."""
from __future__ import annotations

from datetime import datetime

from utils.now import utcnow


def parse_game_datetime(date_str: str, time_str: str) -> datetime | None:
    """Разбирает '25.12' + '20:30' в datetime (год — текущий или следующий).

    Если дата уже прошла в этом году — берётся следующий год.
    """
    try:
        day, month = map(int, date_str.split("."))
        hour, minute = map(int, time_str.split(":"))
    except (ValueError, AttributeError):
        return None

    now = utcnow()
    try:
        dt = datetime(now.year, month, day, hour, minute)
    except ValueError:
        return None
    if dt < now:
        try:
            dt = datetime(now.year + 1, month, day, hour, minute)
        except ValueError:
            return None
    return dt
