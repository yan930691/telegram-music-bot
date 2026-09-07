import asyncio
import logging
import os
import re
import shutil
import tempfile

import aiohttp
import yt_dlp
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    AUDD_API_TOKEN,
    ALLOWED_USERS,
    ADMIN_IDS,
    YOUTUBE_API_KEY,
    YTDL_PROXY,
)
from keyboards.inline import main_menu_kb

router = Router()

# Users waiting for a web-search query
SEARCH_WEB_USERS = set()

# Per-user cached youtube search results (list of info dicts)
WEB_LOOKUP = {}

# URLs we know how to pull audio from
LINK_PATTERN = re.compile(
    r"(youtube\.com|youtu\.be|youtube\.g|tiktok\.com|instagram\.com|"
    r"facebook\.com|twitter\.com|x\.com|soundcloud\.com|pinterest\.com)",
    re.IGNORECASE,
)

_DL_ACTIVE = set()  # users with an in-progress download (avoid double taps)


def _allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


def _in_web_search(message: Message) -> bool:
    return bool(message.from_user) and message.from_user.id in SEARCH_WEB_USERS


def _is_link(message: Message) -> bool:
    return bool(message.text) and bool(LINK_PATTERN.search(message.text))


def web_results_kb(entries=()):
    builder = InlineKeyboardBuilder()
    for i, e in enumerate(entries):
        title = str(e.get("title") or "Unknown")[:32]
        duration = e.get("duration")
        dur = ""
        if duration:
            dur = f" ({int(duration // 60)}:{int(duration % 60):02d})"
        builder.button(text=f"{i + 1}. {title}{dur}", callback_data=f"ytpick:{i}")
    builder.button(text="❌ ပိတ်မည်", callback_data="yt_cancel")
    builder.adjust(1)
    return builder.as_markup()


def _iso_duration_to_seconds(d):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return None
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


async def _yt_search_api(query: str, n: int = 5):
    if not YOUTUBE_API_KEY:
        raise RuntimeError("no api key")
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoCategoryId": "10",  # Music
        "maxResults": n,
        "key": YOUTUBE_API_KEY,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
            search_url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            j = await resp.json()
        if "error" in j:
            raise RuntimeError(str(j["error"]))
        items = [it for it in j.get("items", []) if (it.get("id") or {}).get("videoId")]
        video_ids = [it["id"]["videoId"] for it in items]
        if not video_ids:
            return []

        # fetch durations in one extra call
        durations = {}
        vurl = "https://www.googleapis.com/youtube/v3/videos"
        vparams = {
            "part": "contentDetails",
            "id": ",".join(video_ids),
            "key": YOUTUBE_API_KEY,
        }
        async with session.get(
            vurl,
            params=vparams,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as vresp:
            vj = await vresp.json()
        for v in vj.get("items", []):
            durations[v["id"]] = _iso_duration_to_seconds(
                v.get("contentDetails", {}).get("duration")
            )

    entries = []
    for it in items:
        vid = it["id"]["videoId"]
        entries.append(
            {
                "title": it["snippet"].get("title"),
                "uploader": it["snippet"].get("channelTitle"),
                "duration": durations.get(vid),
                "webpage_url": f"https://www.youtube.com/watch?v={vid}",
            }
        )
    return entries


async def _yt_search(query: str, n: int = 5):
    # Prefer reliable YouTube Data API when a key is set
    if YOUTUBE_API_KEY:
        try:
            entries = await _yt_search_api(query, n)
            if entries:
                return entries
        except Exception as e:
            logging.warning(f"YouTube API search failed, falling back to yt-dlp: {e}")

    def _run():
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "socket_timeout": 30,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
            return info.get("entries") or []

    return await asyncio.wait_for(asyncio.to_thread(_run), timeout=60)


def _build_dl_opts(outdir: str):
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(outdir, "audio.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "nooverwrites": True,
        "socket_timeout": 30,
        # try several YouTube clients in order to dodge bot-detection blocks
        "extractor_args": {
            "youtube": {
                "player_client": ["default", "web_safari", "android", "tv", "ios"]
            }
        },
    }
    if YTDL_PROXY:
        opts["proxy"] = YTDL_PROXY
    if shutil.which("ffmpeg"):
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }
        ]
    return opts


async def _download_audio(url: str):
    """Returns (info_dict, file_path). File lives in a temp dir the caller deletes."""

    def _run():
        outdir = tempfile.mkdtemp()
        opts = _build_dl_opts(outdir)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = None
                for f in os.listdir(outdir):
                    if not f.endswith(".part") and not f.endswith(".ytdl"):
                        path = os.path.join(outdir, f)
                        break
                if not path:
                    raise RuntimeError("No downloaded file found")
                return info, path, outdir
        except Exception:
            shutil.rmtree(outdir, ignore_errors=True)
            raise

    return await asyncio.wait_for(asyncio.to_thread(_run), timeout=180)


def _safe_filename(title: str, ext: str) -> str:
    base = re.sub(r'[\\/:*?"<>|]', "_", title).strip()[:80] or "song"
    return f"{base}.{ext}"


async def _send_audio(message: Message, path: str, info: dict):
    title = str(info.get("title") or "အမည်မသိ")
    uploader = str(info.get("uploader") or info.get("artist") or "")
    ext = path.rsplit(".", 1)[-1]
    filename = _safe_filename(title, ext)
    caption = f"🎵 <b>{title}</b>"
    if uploader:
        caption += f"\n🎤 {uploader}"
    caption += "\n\n📥 Music Bot မှ ဒေါင်းလုဒ် ပြုလုပ်ပြီးပါပြီ!"
    try:
        await message.answer_audio(
            FSInputFile(path, filename=filename),
            title=title,
            performer=uploader,
            caption=caption,
            parse_mode="HTML",
        )
    except Exception:
        await message.answer_document(
            FSInputFile(path, filename=filename),
            caption=caption,
            parse_mode="HTML",
        )


# ---------------- Web search ---------------

@router.callback_query(F.data == "web_search")
async def web_search_prompt(callback: CallbackQuery):
    if not _allowed(callback.from_user.id):
        await callback.answer("🚫 ရရှိခွင့် မရှိပါ!")
        return
    SEARCH_WEB_USERS.add(callback.from_user.id)
    await callback.message.answer(
        "🌐 <b>Web သီချင်းရှာဖွေခြင်း</b>\n\n"
        "သီချင်း နာမည် သို့မဟုတ် အဆိုတော် အမည် ရိုက်ထည့်ပါ 👇\n"
        "ဥပမာ: <code>ချစ်</code> သို့မဟုတ် <code>Ed Sheeran Perfect</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(F.text, _in_web_search)
async def web_search_handler(message: Message):
    user_id = message.from_user.id
    SEARCH_WEB_USERS.discard(user_id)
    query = message.text.strip()
    if not query:
        await message.answer("❌ ရှာဖွေရန် နာမည် ထည့်ပါ။")
        return

    status = await message.answer("⏳ <b>YouTube တွင် ရှာဖွေနေသည်...</b>", parse_mode="HTML")
    try:
        entries = await _yt_search(query)
    except asyncio.TimeoutError:
        await status.edit_text("⏱️ ရှာဖွေရန် ကြာမြင့်နေသည်။ ထပ်ကြိုးစားပါ။")
        return
    except Exception as e:
        logging.warning(f"Web search failed: {e}")
        await status.edit_text(
            "😔 <b>ရှာဖွေ၍ မရပါ။</b>\n\n"
            "YouTube ၏ ကန့်သတ်မှု သို့မဟုတ် နည်းပညာ ပြဿနာ ဖြစ်နိုင်သည်။\n"
            "ခဏအောင့်ပြီး ထပ်ကြိုးစားပါ။"
        )
        return

    if not entries:
        await status.edit_text(f"😔 '{query}' အတွက် သီချင်း မတွေ့ပါ။")
        return

    WEB_LOOKUP[user_id] = entries
    await status.edit_text(
        f"🔍 <b>'{query}' အတွက် ရလဒ် ({len(entries)}):</b>\n\n"
        "ဒေါင်းလုဒ် လုပ်ရန် ရွေးပါ:",
        parse_mode="HTML",
        reply_markup=web_results_kb(entries),
    )


@router.message(F.text, _is_link)
async def link_download(message: Message):
    if not _allowed(message.from_user.id):
        await message.answer("🚫 ရရှိခွင့် မရှိပါ!")
        return
    user_id = message.from_user.id
    if user_id in _DL_ACTIVE:
        await message.answer("⏳ ယခင်ဒေါင်းလုဒ် လုပ်နေဆဲ ဖြစ်သည်။ ခဏစောင့်ပါ။")
        return

    await message.answer(
        "🗜 <b>ရုပ်သံမှ အသံ ခွဲထုတ်နေသည်...</b> (YouTube/TikTok စသည်)\n"
        "ဤအရာမှာ စက္ကန့်အနည်းငယ် ကြာနိုင်သည်။",
        parse_mode="HTML",
    )
    m = re.search(r"https?://[^\s]+", message.text)
    await _perform_download(message, m.group(0) if m else message.text)


@router.callback_query(F.data.startswith("ytpick:"))
async def web_pick(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in _DL_ACTIVE:
        await callback.answer("⏳ ဒေါင်းလုဒ် လုပ်နေဆဲ ဖြစ်သည်။")
        return
    try:
        idx = int(callback.data.split(":")[1])
        entries = WEB_LOOKUP.get(user_id)
        if not entries or idx >= len(entries):
            await callback.answer("⚠️ ရလဒ် သက်တမ်းကုန်ပြီ။ ထပ်ရှာပါ။")
            return
        entry = entries[idx]
    except Exception:
        await callback.answer("⚠️ မမှန်ကန်သော ရွေးချယ်မှု။")
        return

    await callback.message.edit_text(
        "🗜 <b>ဒေါင်းလုဒ် လုပ်နေသည်...</b>\nခဏ စောင့်ပါ...",
        parse_mode="HTML",
    )
    await _perform_download(callback.message, entry.get("webpage_url") or entry.get("url"), user_id)


@router.callback_query(F.data == "yt_cancel")
async def web_cancel(callback: CallbackQuery):
    WEB_LOOKUP.pop(callback.from_user.id, None)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "🎵 မီနူး:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(callback.from_user.id in ADMIN_IDS),
    )
    await callback.answer()


async def _perform_download(message: Message, url: str, user_id=None):
    if user_id is None:
        user_id = message.from_user.id
    if user_id in _DL_ACTIVE:
        return
    _DL_ACTIVE.add(user_id)
    try:
        info, path, outdir = await _download_audio(url)
        try:
            await _send_audio(message, path, info)
        finally:
            shutil.rmtree(outdir, ignore_errors=True)
    except asyncio.TimeoutError:
        await message.answer("⏱️ ဒေါင်းလုဒ် ကြာမြင့်နေသည်။ ထပ်ကြိုးစားပါ။")
    except Exception as e:
        logging.warning(f"Web download failed: {e}")
        await message.answer(
            f"😔 <b>ဒေါင်းလုဒ် မရပါ။</b>\n\n"
            "YouTube ၏ ကန့်သတ်မှု (bot/ဒေတာစင်တာ IP block) သို့မဟုတ် ဖိုင် မရှိတော့ခြင်း ဖြစ်နိုင်သည်။\n"
            f"👉 YouTube မှာ ဖွင့်ကြည့်ရန်: {url}\n"
            "အခြား ရလဒ် သို့မဟုတ် အခြား link စမ်းကြည့်ပါ။"
        )
    finally:
        _DL_ACTIVE.discard(user_id)


# ---------------- Recognition (Shazam-style) ----------------

async def _audd_recognize(data: bytes):
    form = aiohttp.FormData()
    form.add_field("file", data, filename="voice.mp3")
    form.add_field("api_token", AUDD_API_TOKEN)
    form.add_field("return", "apple_music,spotify")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.audd.io/",
            data=form,
            timeout=aiohttp.ClientTimeout(total=90),
        ) as resp:
            return await resp.json()


@router.message(F.voice | F.video_note)
async def recognize_song(message: Message):
    if not _allowed(message.from_user.id):
        await message.answer("🚫 ရရှိခွင့် မရှိပါ!")
        return
    if not AUDD_API_TOKEN:
        await message.answer(
            "🎙 <b>သီချင်း မှတ်မိခြင်း (recognition)</b> မရရှိနိုင်သေးပါ။\n\n"
            "အက်ဒမင်မှ <code>AUDD_API_TOKEN</code> ထည့်သွင်းထားရန် လိုအပ်သည်။",
            parse_mode="HTML",
        )
        return

    file_id = message.voice.file_id if message.voice else message.video_note.file_id
    status = await message.answer("🎙 <b>သီချင်း ခွဲခြားနေသည်...</b>", parse_mode="HTML")
    try:
        file = await message.bot.get_file(file_id)
        data = await message.bot.download_file(file.file_path)
        raw = data.read() if hasattr(data, "read") else data
        result = await _audd_recognize(raw)
    except Exception as e:
        logging.warning(f"Recognition failed: {e}")
        await status.edit_text("😔 <b>ခွဲခြား၍ မရပါ။</b>\nAudio ရှင်းရှင်းလင်းလင်း ဖြစ်ရန် ကြိုးစားပါ။")
        return

    track = (result or {}).get("result")
    if not track:
        await status.edit_text("🤷 <b>ဤသီချင်းကို မှတ်မိနိုင်ခြင်း မရှိပါ။</b>\nပိုရှည်ပြီး ရှင်းသော အပိုင်း ပြန်ပို့ပါ။")
        return

    title = track.get("title") or "အမည်မသိ"
    artist = track.get("artist") or ""
    album = track.get("album") or ""
    lines = [f"🎧 <b>{title}</b>"]
    if artist:
        lines.append(f"🎤 {artist}")
    if album:
        lines.append(f"📀 {album}")
    lines.append("\n🔍 ဒီသီချင်းကို ဒေါင်းလုဒ်လိုပါက \"🌐 Web ရှာ\" ဖြင့် ‌ရှာပါ။")
    await status.edit_text("\n".join(lines), parse_mode="HTML")