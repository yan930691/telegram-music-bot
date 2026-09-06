import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS
from database import db

# Import routers
from handlers import start, music, search, admin

# Import message/song state handlers
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Disable aiogram internal noisy logs a bit
logging.getLogger("aiogram").setLevel(logging.INFO)


async def main():
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register routers
    dp.include_router(start.router)
    dp.include_router(music.router)
    dp.include_router(search.router)
    dp.include_router(admin.router)

    # Connect MongoDB
    await db.connect()
    logging.info("✅ MongoDB connection successful")
    logging.info(f"✅ Bot started. Admins: {ADMIN_IDS}")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
    finally:
        await db.close()
        logging.info("MongoDB connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
