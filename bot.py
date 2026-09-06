import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS, MONGODB_URI
from database import db

# Import routers
from handlers import start, music, search, admin, channel

# Import message/song state handlers
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Disable aiogram internal noisy logs a bit
logging.getLogger("aiogram").setLevel(logging.INFO)


def validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not MONGODB_URI:
        missing.append("MONGODB_URI")
    if not ADMIN_IDS:
        missing.append("ADMIN_IDS")
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): " + ", ".join(missing)
            + "\nPlease set them in Render Dashboard -> Environment."
        )


async def main():
    validate_config()
    logging.info("Config OK: BOT_TOKEN=%s MONGODB_URI=%s ADMIN_IDS=%s",
                 "***" if BOT_TOKEN else None, MONGODB_URI, ADMIN_IDS)

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register routers
    dp.include_router(start.router)
    dp.include_router(music.router)
    dp.include_router(search.router)
    dp.include_router(admin.router)
    dp.include_router(channel.router)

    # Connect MongoDB
    try:
        await db.connect()
        logging.info("MongoDB connection successful")
    except Exception as e:
        logging.exception("MongoDB connection failed")
        raise

    logging.info("Bot starting. Admins: %s", ADMIN_IDS)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
    except Exception:
        logging.exception("Polling crashed")
        raise
    finally:
        await db.close()
        logging.info("MongoDB connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped")
    except SystemExit:
        raise
    except Exception:
        logging.exception("Fatal error")
        sys.exit(1)