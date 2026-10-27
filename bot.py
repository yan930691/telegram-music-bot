import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
import aiohttp

from config import BOT_TOKEN, ADMIN_IDS, MONGODB_URI, BUILD_VERSION
from database import db, AUTO_CATEGORY

# Import routers
from handlers import start, music, search, admin, channel
from handlers.extras import shazam, downloader

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


async def _keepalive_loop():
    """Ping our own URL so Render free tier doesn't auto-sleep after 15 min."""
    url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not url:
        logging.info("Keep-alive disabled (no RENDER_EXTERNAL_URL env set)")
        return
    session = aiohttp.ClientSession()
    try:
        while True:
            await asyncio.sleep(240)
            try:
                async with session.get(
                    f"{url}/health", timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    logging.info("Keep-alive ping -> %s", resp.status)
            except Exception as e:
                logging.warning("Keep-alive ping failed: %s", e)
    finally:
        await session.close()


async def _translate_backfill_task():
    """Translate existing songs (English <-> Myanmar) for bilingual search."""
    try:
        n = await db.backfill_translations()
        if n:
            logging.info("Translated %s song(s) for bilingual search", n)
        else:
            logging.info("Translation backfill: nothing to do")
    except Exception:
        logging.exception("Translation backfill failed")


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
    logging.info("Build version: %s", BUILD_VERSION)
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
    dp.include_router(downloader.router)
    dp.include_router(shazam.router)
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

    added = await db.seed_default_categories()
    if added:
        logging.info("Seeded default categories: %s", ", ".join(added))

    # Make sure albums saved without a category (channel auto-save, forwards) or
    # pointing at a deleted category are visible in the category browser.
    auto_cat = await db.get_or_create_category(AUTO_CATEGORY)
    if auto_cat:
        cats = await db.get_categories()
        valid_ids = [c["_id"] for c in cats]
        moved = await db.backfill_album_categories(auto_cat["_id"], valid_ids)
        if moved:
            logging.info("Moved %s album(s) into '%s'", moved, AUTO_CATEGORY)

    asyncio.create_task(_keepalive_loop())

    # Translate existing songs (English <-> Myanmar) so both can be searched.
    # Idempotent: only songs missing ``search_terms`` are processed.
    asyncio.create_task(_translate_backfill_task())

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