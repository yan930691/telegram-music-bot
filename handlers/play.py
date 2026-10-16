"""Voice-chat playback commands (aiogram side).

The heavy lifting (joining the call + streaming) is done by utils.stream using
a Pyrogram assistant; here we only parse commands, resolve/download media and
send the messages/buttons.
"""

import logging
import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import (
    ADMIN_IDS,
    DOWNLOADS_DIR,
    DURATION_LIMIT,
    QUEUE_LIMIT,
    STREAM_ENABLED,
    VIDEO_PLAY,
)
from utils import formatters as fmt
from utils.stream import StreamError, stream, vc_controls_kb
from utils.ytdl import ResolveError, Track, fmt_duration, resolve

router = Router()
log = logging.getLogger("play")

GROUP_TYPES = ("group", "supergroup")


def _parse_command(message: Message):
    raw = message.text or message.caption or ""
    parts = raw.split()
    if not parts:
        return "play", False, ""
    cmd = parts[0].lstrip("/")
    cmd = cmd.split("@")[0].lower()
    video = cmd.startswith("v")
    rest = parts[1:]
    if "-v" in rest:
        video = True
    rest = [p for p in rest if p not in ("-v", "-f")]
    return cmd, video, " ".join(rest).strip()


def _reply_media(message: Message):
    reply = message.reply_to_message
    if not reply:
        return None
    return reply.audio or reply.video or reply.voice or reply.document


def _reply_url(message: Message):
    reply = message.reply_to_message
    if not reply:
        return ""
    text = reply.text or reply.caption or ""
    for token in text.split():
        if token.startswith("http://") or token.startswith("https://"):
            return token
    return ""


async def _is_authorized(message: Message, chat_id: int) -> bool:
    if message.from_user and message.from_user.id in ADMIN_IDS:
        return True
    cur = stream.get_current(chat_id)
    if cur and cur.requester_id == getattr(message.from_user, "id", 0):
        return True
    try:
        member = await message.bot.get_chat_member(chat_id, message.from_user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def _telegram_track(message: Message, media, video: bool) -> Track:
    ext = ".mp4" if video else ".mp3"
    fname = getattr(media, "file_name", None)
    if fname and "." in fname:
        ext = os.path.splitext(fname)[1]
    dest = os.path.join(DOWNLOADS_DIR, f"tg_{media.file_unique_id}{ext}")
    if not os.path.exists(dest):
        await message.bot.download(media, destination=dest)
    title = fname or getattr(media, "title", None) or "Telegram media"
    dur = getattr(media, "duration", 0) or 0
    mention = message.from_user.mention_html() if message.from_user else "-"
    track = Track(
        id=str(media.file_unique_id),
        title=title,
        duration_sec=int(dur),
        duration=fmt_duration(dur),
        file_path=dest,
        requester=mention,
        video=video,
    )
    track.requester_id = getattr(message.from_user, "id", 0)
    return track


@router.message(Command("play", "p", "vplay", "v", "song", "vsong"))
async def play_handler(message: Message):
    if not STREAM_ENABLED:
        await message.reply(
            "⚠️ VC streaming မဖွင့်ထားပါ။ API_ID / API_HASH / SESSION သတ်မှတ်ပါ။"
        )
        return
    if message.chat.type not in GROUP_TYPES:
        await message.reply(fmt.vc_need_group())
        return

    chat_id = message.chat.id
    _, video, query = _parse_command(message)
    video = video and VIDEO_PLAY
    mention = message.from_user.mention_html() if message.from_user else "-"
    requester_id = getattr(message.from_user, "id", 0)

    media = _reply_media(message)
    if not media and not query:
        query = _reply_url(message)

    status = await message.reply(fmt.vc_searching())

    # ---- build track list ----
    try:
        if media:
            await status.edit_text(fmt.vc_downloading())
            track = await _telegram_track(message, media, video)
            tracks = [track]
        else:
            tracks = await resolve(query, video=video, requester=mention)
    except ResolveError as e:
        await status.edit_text(fmt.vc_error(e))
        return
    except Exception:
        log.exception("play resolve failed")
        await status.edit_text(fmt.vc_error())
        return

    for t in tracks:
        t.requester_id = requester_id

    # ---- enqueue or play now ----
    try:
        if stream.active(chat_id):
            if len(stream.get_queue(chat_id)) >= QUEUE_LIMIT:
                await status.edit_text(
                    f"⚠️ တန်းစီစာရင်း ပြည့်နေပါပြီ ({QUEUE_LIMIT})။"
                )
                return
            first_pos = None
            for t in tracks:
                pos = stream.enqueue(chat_id, t)
                if first_pos is None:
                    first_pos = pos
            await status.edit_text(
                fmt.vc_added_queue(first_pos, tracks[0].title, tracks[0].requester)
            )
            return

        # not active -> play the first track now
        await status.edit_text(fmt.vc_downloading())
        ok = await stream.ensure_assistant(chat_id)
        if not ok:
            await status.edit_text(fmt.vc_assistant_missing())
            return
        first = tracks[0]
        await stream.begin(chat_id, first)
        for t in tracks[1:]:
            stream.enqueue(chat_id, t)
        await status.edit_text(
            fmt.vc_now_playing(first.title, first.duration, first.requester),
            parse_mode="HTML",
            reply_markup=vc_controls_kb(chat_id),
        )
        if len(tracks) > 1:
            await message.answer(
                fmt.vc_added_queue(len(tracks) - 1, tracks[-1].title, tracks[-1].requester)
            )
    except StreamError as e:
        if e.code == "no-active-call":
            await status.edit_text(fmt.vc_no_active_call())
        elif e.code == "duration-limit":
            await status.edit_text(
                f"⚠️ မိနစ် {DURATION_LIMIT // 60} ထက်ပိုသော သီချင်းကို ဖွင့်ခွင့်မပြုပါ။"
            )
        elif e.code.startswith("libs-missing") or e.code == "no-session":
            await status.edit_text(
                "⚠️ Streaming library/session မရှိပါ။ requirements install နှင့် SESSION စစ်ပါ။"
            )
        else:
            await status.edit_text(fmt.vc_error(e.code))
    except Exception:
        log.exception("play failed")
        await status.edit_text(fmt.vc_error())


@router.message(Command("pause"))
async def pause_handler(message: Message):
    chat_id = message.chat.id
    if not stream.active(chat_id):
        await message.reply(fmt.vc_not_playing())
        return
    if not await _is_authorized(message, chat_id):
        await message.reply("❌ ခွင့်ပြုချက် မရှိပါ။")
        return
    ok = await stream.pause(chat_id)
    await message.reply(fmt.vc_paused() if ok else fmt.vc_error())


@router.message(Command("resume", "r"))
async def resume_handler(message: Message):
    chat_id = message.chat.id
    if not stream.active(chat_id):
        await message.reply(fmt.vc_not_playing())
        return
    if not await _is_authorized(message, chat_id):
        await message.reply("❌ ခွင့်ပြုချက် မရှိပါ။")
        return
    ok = await stream.resume(chat_id)
    await message.reply(fmt.vc_resumed() if ok else fmt.vc_error())


@router.message(Command("skip", "next"))
async def skip_handler(message: Message):
    chat_id = message.chat.id
    if not stream.active(chat_id):
        await message.reply(fmt.vc_not_playing())
        return
    if not await _is_authorized(message, chat_id):
        await message.reply("❌ ခွင့်ပြုချက် မရှိပါ။")
        return
    await message.reply(fmt.vc_skipped())
    await stream.play_next(chat_id)


@router.message(Command("stop", "end"))
async def stop_handler(message: Message):
    chat_id = message.chat.id
    if not stream.active(chat_id):
        await message.reply(fmt.vc_not_playing())
        return
    if not await _is_authorized(message, chat_id):
        await message.reply("❌ ခွင့်ပြုချက် မရှိပါ။")
        return
    await stream.stop(chat_id)
    await message.reply(fmt.vc_stopped())


@router.message(Command("seek"))
async def seek_handler(message: Message):
    chat_id = message.chat.id
    if not stream.active(chat_id):
        await message.reply(fmt.vc_not_playing())
        return
    if not await _is_authorized(message, chat_id):
        await message.reply("❌ ခွင့်ပြုချက် မရှိပါ။")
        return
    arg = message.text.split(maxsplit=1)
    if len(arg) < 2 or not arg[1].strip().isdigit():
        await message.reply("အသုံးပြုပုံ: <code>/seek 60</code>", parse_mode="HTML")
        return
    await stream.seek(chat_id, int(arg[1].strip()))
    await message.reply(f"⏩ {arg[1].strip()} စက္ကန့်မှ စတင်ဖွင့်သည်။")


@router.message(Command("queue", "q"))
async def queue_handler(message: Message):
    chat_id = message.chat.id
    items = stream.get_queue(chat_id)
    if not items:
        await message.reply(fmt.vc_not_playing())
        return
    lines = [fmt.vc_queue_header(), ""]
    for i, t in enumerate(items, start=1):
        marker = "▶️ " if i == 1 else ""
        lines.append(marker + fmt.vc_queue_item(i, t.title, t.duration, t.requester))
    await message.reply("\n".join(lines), parse_mode="HTML")


# ------------------------------ button callbacks ------------------------------
@router.callback_query(F.data.startswith("vc:"))
async def vc_controls(callback: CallbackQuery):
    action = callback.data.split(":", 1)[1]
    chat_id = callback.message.chat.id
    if not stream.active(chat_id):
        await callback.answer(fmt.vc_not_playing(), show_alert=True)
        return
    authorized = callback.from_user.id in ADMIN_IDS
    if not authorized:
        cur = stream.get_current(chat_id)
        if cur and cur.requester_id == callback.from_user.id:
            authorized = True
        else:
            try:
                member = await callback.bot.get_chat_member(chat_id, callback.from_user.id)
                authorized = member.status in ("administrator", "creator")
            except Exception:
                authorized = False
    if not authorized:
        await callback.answer("❌ ခွင့်ပြုချက် မရှိပါ။", show_alert=True)
        return

    if action == "pause":
        await stream.pause(chat_id)
        await callback.answer(fmt.vc_paused())
    elif action == "resume":
        await stream.resume(chat_id)
        await callback.answer(fmt.vc_resumed())
    elif action == "skip":
        await callback.answer(fmt.vc_skipped())
        await stream.play_next(chat_id)
    elif action == "stop":
        await stream.stop(chat_id)
        await callback.answer(fmt.vc_stopped())
    else:
        await callback.answer()
