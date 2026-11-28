"""Admin commands for the movie watcher. Existing bot handlers are untouched."""

import asyncio
import logging
import os

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_IDS
import watcher

router = Router()
_scan_lock = asyncio.Lock()

log = logging.getLogger(__name__)


def _credentials():
    raw_id = os.getenv("WATCH_API_ID") or os.getenv("TG_API_ID") or ""
    api_hash = os.getenv("WATCH_API_HASH") or os.getenv("TG_API_HASH") or ""
    session = os.getenv("WATCH_SESSION") or os.getenv("TG_SESSION") or ""
    try:
        api_id = int(raw_id)
    except (TypeError, ValueError):
        api_id = 0
    return api_id, api_hash.strip(), session.strip()


async def run_scan(dry_run: bool = False):
    """Run one watcher scan. Never raises, so the bot keeps running."""
    api_id, api_hash, session = _credentials()
    if not (api_id and api_hash and session):
        return False, (
            "Watcher session မရှိသေးပါ။ Render env မှာ "
            "WATCH_API_ID / WATCH_API_HASH / WATCH_SESSION ထည့်ပါ။"
        )

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    client = TelegramClient(StringSession(session), api_id, api_hash)
    try:
        await client.connect()
        state = watcher.State(watcher.STATE_FILE)
        await watcher.scan_once(client, state, dry_run=dry_run)
        state.save()
        return True, "စစ်ဆေးမှု ပြီးပါပြီ။"
    except Exception as exc:
        watcher.log("watch command error: " + type(exc).__name__)
        return False, "scan error: " + type(exc).__name__
    finally:
        await client.disconnect()


async def _reply(message: Message, dry_run: bool) -> None:
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        await message.answer("Admin only ပါကွာ။")
        return
    if _scan_lock.locked():
        await message.answer("စစ်ဆေးမှု ရှိနေပြီးသားပါ — စောင့်ပေးပါကွာ။")
        return

    async with _scan_lock:
        await message.answer("စောင့်ကြည့်စစ်ဆေးမှု စနေပါပြီ...")
        ok, text = await run_scan(dry_run=dry_run)
    await message.answer(("✅ " if ok else "⚠️ ") + text)


@router.message(Command("watch"))
async def watch_command(message: Message):
    await _reply(message, dry_run=False)


@router.message(Command("watchdry"))
async def watch_dry_command(message: Message):
    await _reply(message, dry_run=True)


async def watch_worker(bot) -> None:
    """Keep the 9/12/17/21/22 MMT schedule without stopping the bot."""
    while True:
        try:
            seconds, _ = watcher.seconds_to_next_slot()
            await asyncio.sleep(max(1.0, seconds))
            if _scan_lock.locked():
                continue
            async with _scan_lock:
                ok, text = await run_scan(dry_run=False)
            if not ok:
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id, "⚠️ watcher: " + text)
                    except Exception:
                        log.warning("cannot notify admin about watcher error")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            watcher.log("watch_worker error: " + type(exc).__name__)
            await asyncio.sleep(60)
