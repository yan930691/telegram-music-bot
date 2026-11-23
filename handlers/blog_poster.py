import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_IDS

router = Router()
log = logging.getLogger(__name__)

# Set from bot.py
_poster = None


def set_poster(poster):
    global _poster
    _poster = poster


@router.message(Command("post10"))
async def cmd_post10(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not _poster:
        await message.answer("❌ Blog poster not configured")
        return
    if _poster.is_running:
        await message.answer("⏳ Already processing, please wait")
        return

    # Check daily limit first
    status = await _poster.get_status()
    if status["today_count"] >= status["daily_limit"]:
        await message.answer(
            f"⚠️ Daily limit reached: {status['today_count']}/{status['daily_limit']}\n"
            f"Try again tomorrow."
        )
        return

    await message.answer(
        f"🚀 Starting batch...\n"
        f"📊 Today: {status['today_count']}/{status['daily_limit']}\n"
        f"⏱ This will take 10-20 minutes (processing in background)"
    )

    asyncio.create_task(_run_batch(message))


async def _run_batch(message: Message):
    try:
        result = await _poster.process_batch(count=10)

        if not result.get("ok"):
            if result.get("reason") == "daily_limit":
                await message.answer(
                    f"⚠️ Daily limit: {result['used']}/{result['limit']}"
                )
            elif result.get("reason") == "already_running":
                await message.answer("⏳ Already running")
            else:
                await message.answer(f"❌ Failed: {result.get('reason')}")
            return

        if result.get("processed", 0) == 0 and result.get("reason") == "nothing_new":
            await message.answer("✅ No unprocessed posts left!")
            return

        await message.answer(
            f"✅ Batch complete!\n"
            f"• Posted: {result.get('processed', 0)}\n"
            f"• Failed: {result.get('failed', 0)}\n"
            f"• Today: {result.get('used', 0)}/{result.get('limit', 10)}"
        )
    except Exception:
        log.exception("batch failed")
        try:
            await message.answer("❌ Batch failed (check logs)")
        except Exception:
            pass


@router.message(Command("poststatus"))
async def cmd_status(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not _poster:
        return
    s = await _poster.get_status()
    await message.answer(
        f"📊 Blog Poster Status\n"
        f"• Today: {s['today_count']}/{s['daily_limit']}\n"
        f"• Total seen: {s['seen_count']}\n"
        f"• Running: {'yes' if s['running'] else 'no'}"
    )
