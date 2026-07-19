"""Единый источник текущего времени (naive UTC).

Python 3.12+ помечает datetime.utcnow() устаревшим. Но в БД (SQLite)
хранятся naive-даты, поэтому нужен naive UTC без предупреждений.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Текущее время в UTC без tzinfo (naive), совместимо с БД."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
