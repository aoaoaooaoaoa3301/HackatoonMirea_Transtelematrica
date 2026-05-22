import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from app.config import settings
from app.handlers import router

logging.basicConfig(level=logging.INFO)

BOT_COMMANDS = [
    BotCommand(command="my", description="Мои задачи"),
    BotCommand(command="week", description="Задачи на неделю"),
    BotCommand(command="deadlines", description="Ближайшие дедлайны"),
    BotCommand(command="risks", description="Задачи в зоне риска"),
    BotCommand(command="team", description="Сводка по команде"),
    BotCommand(command="overload", description="Кто перегружен"),
    BotCommand(command="clear", description="Очистить историю чата с AI"),
    BotCommand(command="link", description="Привязать аккаунт (/link КОД)"),
    BotCommand(command="help", description="Справка по командам"),
]


async def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty. Set it to start the Telegram bot.")

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    # Register the command menu so users get the "/" autocomplete list.
    await bot.set_my_commands(BOT_COMMANDS)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
