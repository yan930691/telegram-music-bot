import asyncio
import logging
import os
import re
import tempfile

import yt_dlp
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import FSInputFile, Message

router = Router()
logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _extract_url(text: str) -> str | None:
    if not text:
        return None
    m = URL_RE.search(text)
    if not m:
        return None
    return m.group(0).strip()


async def _download_media(url: str) -> str | None:
    outdir = tempfile.mkdtemp(prefix="dl_")
    outtmpl = os.path.join(outdir, "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "max_filesize": 50 * 1024 * 1024,
    }
    try:
        loop = asyncio.get_running_loop()
        def _run():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None
                # find downloaded file
                fn = ydl.prepare_filename(info)
                if os.path.exists(fn):
                    return fn
                # try merged
                base = os.path.splitext(fn)[0]
                for ext in ("mp4", "mkv", "webm", "mov"):
                    p = base + "." + ext
                    if os.path.exists(p):
                        return p
                return None
        return await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.warning("yt-dlp failed %s", e)
        return None


async def _download_audio(url: str) -> str | None:
    outdir = tempfile.mkdtemp(prefix="dla_")
    outtmpl = os.path.join(outdir, "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    }
    try:
        loop = asyncio.get_running_loop()
        def _run():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None
                base = os.path.splitext(ydl.prepare_filename(info))[0]
                for p in (base + ".mp3", base + ".m4a", base + ".opus"):
                    if os.path.exists(p):
                        return p
                return None
        return await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.warning("yt-dlp audio failed %s", e)
        return None


@router.message(F.text)
async def link_handler(message: Message):
    if message.chat.type != ChatType.PRIVATE:
        return
    text = message.text or ""
    url = _extract_url(text)
    if not url:
        return
    lower = url.lower()
    wait = None
    path = None
    is_audio = any(x in lower for x in ("music", "audio", "mp3"))
    try:
        wait = await message.reply_text("⬇️ ဒေါင်းလုပ်နေပါသည်...")
        if is_audio:
            path = await _download_audio(url)
        else:
            path = await _download_media(url)
        if not path or not os.path.exists(path):
            if wait:
                try:
                    await wait.edit_text("❌ ဒေါင်းမရပါ။ Link ကို စစ်ဆေးပေးပါ။")
                except Exception:
                    await message.reply_text("❌ ဒေါင်းမရပါ။ Link ကို စစ်ဆေးပေးပါ။")
            return
        if path.endswith(".mp3"):
            if wait:
                try:
                    await wait.edit_text("📤 ပို့နေပါသည်...")
                except Exception:
                    pass
            await message.reply_audio(FSInputFile(path))
        else:
            if wait:
                try:
                    await wait.edit_text("📤 ပို့နေပါသည်...")
                except Exception:
                    pass
            await message.reply_video(FSInputFile(path), supports_streaming=True)
        if wait:
            try:
                await wait.delete()
            except Exception:
                pass
    except Exception as e:
        logger.exception("download send failed")
        try:
            if wait:
                await wait.edit_text(f"❌ အမှားဖြစ်သွားပါသည်: {html_escape(str(e)[:150])}")
            else:
                await message.reply_text(f"❌ အမှားဖြစ်သွားပါသည်: {html_escape(str(e)[:150])}")
        except Exception:
            pass
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                d = os.path.dirname(path)
                try:
                    os.rmdir(d)
                except Exception:
                    pass
            except Exception:
                pass


def html_escape(s: str) -> str:
    import html as h
    return h.escape(s)
