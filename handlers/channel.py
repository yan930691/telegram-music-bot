import logging

from aiogram import Router, F
from aiogram.types import Message

from database import db
from config import CHANNEL_ID
from utils.formatters import split_caption
from utils.converter import normalize_myanmar
from utils.metadata import read_audio_metadata

router = Router()

DEFAULT_ALBUM = "ချန်နယ် စုစည်းမှု"

_bot_id = None


async def _get_bot_id(message: Message):
    global _bot_id
    if _bot_id is None:
        me = await message.bot.get_me()
        _bot_id = me.id
    return _bot_id


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
        parts = split_caption(caption)
        for i in range(len(parts)):
            parts[i] = normalize_myanmar(parts[i])

        # Caption formats: "AlbumName | SongTitle" or "AlbumName | SongTitle | Artist"
        album_name = None
        custom_title = None
        artist_name = performer
        if len(parts) >= 3:
            album_name = parts[0]
            custom_title = parts[1]
            artist_name = parts[2] or performer
        elif len(parts) == 2:
            album_name = parts[0]
            custom_title = parts[1]
        elif len(parts) == 1:
            album_name = parts[0]

        if custom_title:
            title = custom_title

        # Fill gaps from the file's embedded metadata (album is never sent by
        # Telegram, so MP3 ID3 tags are the only reliable source for it).
        if not title or not performer or not album_name:
            meta = await read_audio_metadata(message.bot, file_id, file_size)
            if not title and meta.get("title"):
                title = meta["title"]
            if not performer and meta.get("artist"):
                performer = meta["artist"]
            if not album_name and meta.get("album"):
                album_name = meta["album"]
            if artist_name in (None, "") and performer:
                artist_name = performer

        if not title:
            title = "အမည်မသိ"
        if not album_name:
            album_name = DEFAULT_ALBUM
        title = normalize_myanmar(title)
        artist_name = normalize_myanmar(artist_name)
        album_name = normalize_myanmar(album_name)

        # Skip duplicates (same file_id already saved)
        existing = await db.db.songs.find_one({"file_id": file_id})
        if existing:
            await message.reply("ℹ️ ဤသီချင်းကို သိမ်းပြီးသား ဖြစ်ပါသည်။")
            return

        artist = await db.get_or_create_artist(artist_name or "အမည်မသိ")
        album = await db.get_or_create_album(
            album_name,
            artist=artist["name"],
            category_id=None,
            artist_id=artist["_id"],
        )
        await db.add_song(
            title,
            album["_id"],
            file_id,
            file_size,
            duration,
            artist_id=artist["_id"],
        )

        await message.reply(
            f"✅ <b>သီချင်းအသစ် ရောက်ရှိပါပြီ!</b>\n\n"
            f"🎧 {title}\n"
            f"🎤 {artist['name']}\n"
            f"📀 {album_name}\n\n"
            "🤖 Bot မှ ရယူလိုပါက bot chat သို့ ဝင်ရောက်ပါ",
            parse_mode="HTML",
        )
    except Exception as e:
        logging.warning(f"Channel auto-save failed: {e}")