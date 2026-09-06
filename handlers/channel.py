import logging

from aiogram import Router, F
from aiogram.types import Message

from database import db
from config import CHANNEL_ID

router = Router()

DEFAULT_ALBUM = "ချန်နယ် စုစည်းမှု"

_bot_id = None


async def _get_bot_id(message: Message):
    global _bot_id
    if _bot_id is None:
        me = await message.bot.get_me()
        _bot_id = me.id
    return _bot_id


async def get_or_create_album(name: str):
    album = await db.db.albums.find_one({"name": name})
    if album:
        return album
    result = await db.add_album(name, "", None)
    return await db.db.albums.find_one({"_id": result.inserted_id})


@router.channel_post(F.audio | F.document)
async def on_channel_audio(message: Message):
    try:
        # Ignore messages posted by the bot itself (e.g. release announcements)
        if message.from_user and message.from_user.id == await _get_bot_id(message):
            return

        if message.audio:
            file_id = message.audio.file_id
            file_size = message.audio.file_size or 0
            duration = message.audio.duration or 0
            title = message.audio.title or ""
            performer = message.audio.performer or ""
        elif message.document:
            mime = (message.document.mime_type or "")
            if "audio" not in mime:
                return
            file_id = message.document.file_id
            file_size = message.document.file_size or 0
            duration = 0
            title = message.document.file_name or ""
            performer = ""
        else:
            return

        caption = message.caption or ""

        # Caption format: "AlbumName | SongTitle"
        album_name = None
        custom_title = None
        if "|" in caption:
            parts = caption.split("|", 1)
            album_name = parts[0].strip()
            custom_title = parts[1].strip()

        if custom_title:
            title = custom_title
        if not title:
            title = "အမည်မသိ"
        if not album_name:
            album_name = DEFAULT_ALBUM

        # Skip duplicates (same file_id already saved)
        existing = await db.db.songs.find_one({"file_id": file_id})
        if existing:
            await message.reply("ℹ️ ဤသီချင်းကို သိမ်းပြီးသား ဖြစ်ပါသည်။")
            return

        album = await get_or_create_album(album_name)
        await db.add_song(title, album["_id"], file_id, file_size, duration)

        await message.reply(
            f"✅ <b>သီချင်းအသစ် ရောက်ရှိပါပြီ!</b>\n\n"
            f"🎧 {title}\n"
            f"📀 {album_name}\n\n"
            "🤖 Bot မှ ရယူလိုပါက bot chat သို့ ဝင်ရောက်ပါ",
            parse_mode="HTML",
        )
    except Exception as e:
        logging.warning(f"Channel auto-save failed: {e}")