import asyncio
import html
import logging
import os
import tempfile

import aiohttp
import imageio_ffmpeg
from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from config import AUDD_API_KEY

router = Router()
logger = logging.getLogger(__name__)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


async def _download(bot: Bot, file_id: str, dest: str) -> bool:
    try:
        f = await bot.get_file(file_id)
        await bot.download_file(f.file_path, destination=dest)
        return True
    except Exception as e:
        logger.warning("download failed %s", e)
        return False


async def _extract_audio(src: str, dst: str, max_seconds: int = 12) -> bool:
    proc = await asyncio.create_subprocess_exec(
        FFMPEG,
        "-y",
        "-i",
        src,
        "-t",
        str(max_seconds),
        "-vn",
        "-ar",
        "44100",
        "-ac",
        "1",
        "-f",
        "mp3",
        dst,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    return proc.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0


async def _recognize_file(path: str) -> dict | None:
    if not AUDD_API_KEY:
        return None
    f = None
    try:
        data = aiohttp.FormData()
        data.add_field("api_token", AUDD_API_KEY)
        f = open(path, "rb")
        data.add_field("file", f, filename="audio.mp3")
        data.add_field("return", "apple_music,spotify")
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.audd.io/", data=data, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                js = await resp.json()
        if js.get("status") == "success" and js.get("result"):
            return js["result"]
    except Exception as e:
        logger.warning("audd failed %s", e)
    finally:
        if f:
            try:
                f.close()
            except Exception:
                pass
    return None


def _fmt_res(r: dict) -> str:
    title = html.escape(r.get("title") or "Unknown")
    artist = html.escape(r.get("artist") or "")
    album = html.escape(r.get("album") or "")
    out = f"🎵 <b>{title}</b>"
    if artist:
        out += f"\n👤 {artist}"
    if album:
        out += f"\n💿 {album}"
    links = []
    am = (r.get("apple_music") or {}).get("url")
    sp = ((r.get("spotify") or {}).get("external_urls") or {}).get("spotify")
    if am:
        links.append(f'<a href="{html.escape(am)}">Apple Music</a>')
    if sp:
        links.append(f'<a href="{html.escape(sp)}">Spotify</a>')
    if links:
        out += "\n\n" + " | ".join(links)
    return out


async def _handle_audio_message(message: Message, bot: Bot):
    if not AUDD_API_KEY:
        await message.reply_text("❌ AUDD_API_KEY မသတ်မှတ်ရသေးပါ။")
        return
    src = None
    dst = None
    try:
        wait = await message.reply_text("🔍 သီချင်းကို ရှာနေပါသည်...")
        if message.voice:
            fid = message.voice.file_id
        elif message.audio:
            fid = message.audio.file_id
        elif message.video_note:
            fid = message.video_note.file_id
        elif message.video:
            fid = message.video.file_id
        else:
            await wait.edit_text("ရှာဖွေနိုင်တဲ့ အသံ/ဗီဒီယိုကို ပို့ပေးပါ။")
            return
        src = tempfile.mktemp(suffix=".bin")
        if not await _download(bot, fid, src):
            await wait.edit_text("❌ ဖိုင်ဒေါင်းမရပါ။")
            return
        dst = tempfile.mktemp(suffix=".mp3")
        if not await _extract_audio(src, dst):
            await wait.edit_text("❌ အသံထုတ်လို့မရပါ။")
            return
        res = await _recognize_file(dst)
        if not res:
            await wait.edit_text("❌ သီချင်းမတွေ့ပါ။ နောက်တစ်ကြိမ် ထပ်စမ်းကြည့်ပါ။")
            return
        await wait.edit_text(_fmt_res(res), disable_web_page_preview=True)
    finally:
        for p in (src, dst):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@router.message(F.voice | F.audio | F.video_note | F.video)
async def shazam_handler(message: Message):
    if message.chat.type != ChatType.PRIVATE:
        return
    await _handle_audio_message(message, message.bot)
