import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import settings
from app.handlers import router

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty. Set it to start the Telegram bot.")

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
