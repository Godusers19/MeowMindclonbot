"""Конфигурация бота: читается из .env через python-dotenv."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    owner_id: int
    database_url: str = "sqlite+aiosqlite:///./meowmind.db"

    # Веб-панель
    web_host: str = "127.0.0.1"
    web_port: int = 8080
    web_secret: str = "change-me"
    web_login: str = "admin"
    web_password: str = "admin"


def _default_db_url() -> str:
    """SQLite-путь.

    На Amvera (и любом хостинге) постоянный диск монтируется в /data —
    всё, что вне его, стирается при redeploy. Если каталог /data есть,
    кладём базу туда, иначе — рядом с кодом (локальная разработка).
    """
    if os.path.isdir("/data"):
        return "sqlite+aiosqlite:////data/meowmind.db"
    return "sqlite+aiosqlite:///./meowmind.db"


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "your_bot_token_here":
        raise RuntimeError(
            "BOT_TOKEN не задан. Укажи токен от @BotFather в файле .env"
        )

    return Config(
        bot_token=token,
        owner_id=int(os.getenv("OWNER_ID", "0") or "0"),
        database_url=os.getenv("DATABASE_URL", _default_db_url()),
        web_host=os.getenv("WEB_HOST", "127.0.0.1"),
        web_port=int(os.getenv("WEB_PORT", "8080")),
        web_secret=os.getenv("WEB_SECRET", "change-me"),
        web_login=os.getenv("WEB_LOGIN", "admin"),
        web_password=os.getenv("WEB_PASSWORD", "admin"),
    )


config = load_config()
