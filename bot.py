import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

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


async def health_handler(request: web.Request):
    return web.Response(text="OK")


async def _start_health_server():
    """Minimal web server so Render's port scan passes (bots have no web listener)."""
    port = int(os.getenv("PORT", 8000))
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Health server started on port %s", port)
    return runner


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

    runner = None
    try:
        runner = await _start_health_server()
    except Exception:
        logging.exception("Health server failed to start (continuing anyway)")

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
        if runner:
            await runner.cleanup()
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