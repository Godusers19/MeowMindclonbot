"""Точка входа: запуск бота и веб-панели localhost."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import config
from database.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("meowmind")


def build_bot() -> Bot:
    """Создаёт экземпляр Bot."""
    return Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def setup_handlers(dp: Dispatcher) -> None:
    """Подключение роутеров модулей (заполняется по мере разработки)."""
    from handlers import (
        economy, moderation, caps, lists, shop, custom_cmd, games, help,
    )

    dp.include_router(help.router)
    dp.include_router(economy.router)
    dp.include_router(moderation.router)
    dp.include_router(caps.router)
    dp.include_router(lists.router)
    dp.include_router(shop.router)
    dp.include_router(games.router)
    dp.include_router(custom_cmd.router)

    # динамический вызов .триггер — регистрируется ПОСЛЕДНИМ,
    # чтобы не перехватывать встроенные команды
    dp.include_router(custom_cmd.dynamic_router)


def setup_middlewares(dp: Dispatcher) -> None:
    """Подключение middlewares (авто-регистрация и т.д.)."""
    from middlewares.registration import ChatMemberMiddleware, RegistrationMiddleware

    dp.message.middleware(RegistrationMiddleware())
    # апдейты вступил/вышел — нужен бот-админ и allowed_updates ниже
    dp.chat_member.middleware(ChatMemberMiddleware())


async def main() -> None:
    logger.info("Инициализация базы данных...")
    await init_db()

    logger.info("Запуск бота...")
    bot = build_bot()
    me = await bot.get_me()
    logger.info("Бот запущен: @%s (id=%s)", me.username, me.id)

    dp = Dispatcher()
    setup_middlewares(dp)
    setup_handlers(dp)

    # планировщик: авто-опросы по расписанию
    from handlers import games as games_handler
    from services.scheduler import start as start_scheduler, shutdown as stop_scheduler

    games_handler.set_bot(bot)
    start_scheduler()

    # веб-панель на localhost параллельно с ботом
    web_task = asyncio.create_task(start_web())

    try:
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "edited_message",
                "callback_query",
                "chat_member",
                "my_chat_member",
            ],
        )
    finally:
        stop_scheduler()
        web_task.cancel()
        await bot.session.close()


async def start_web() -> None:
    """Запускает FastAPI-панель через uvicorn в общем event loop."""
    import uvicorn

    from web.app import app

    uconfig = uvicorn.Config(
        app,
        host=config.web_host,
        port=config.web_port,
        log_level="warning",
    )
    server = uvicorn.Server(uconfig)
    logger.info(
        "Веб-панель: http://%s:%s (логин: %s)",
        config.web_host, config.web_port, config.web_login,
    )
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановлено.")
