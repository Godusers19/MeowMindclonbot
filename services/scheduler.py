"""Общий планировщик APScheduler.

Используется для напоминаний об играх и авто-опросов.
Инициализируется в main при запуске; хендлеры добавляют/удаляют задачи.
"""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


def start() -> None:
    if not scheduler.running:
        scheduler.start()


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
