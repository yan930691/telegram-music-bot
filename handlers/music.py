import html
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from bson import ObjectId
from keyboards.inline import album_songs_to_send

router = Router()


async def _safe_answer(callback: CallbackQuery, text: str):
    try:
        await callback.answer(text)
    except Exception:
        pass


async def _build_caption(song) -> str:
    lines = [f"🎵 <b>{html.escape(song['title'])}</b>"]
    if song.get("artist_id"):
        artist = await db.get_artist(song["artist_id"])
        if artist:
            lines.append(f"🎤 {html.escape(artist['name'])}")
    album = await db.get_album(song["album_id"])
    if album:
        lines.append(f"📀 {html.escape(album['name'])}")
    return "\n".join(lines)


@router.callback_query(F.data.startswith("song:"))
async def send_song(callback: CallbackQuery):
    try:
        song_id = ObjectId(callback.data.split(":")[1])
        song = await db.get_song(song_id)
        if not song:
            await _safe_answer(callback, "❌ သီချင်းမတွေ့ပါ!")
            return
        try:
            await db.increment_song_downloads(song_id)
            await db.increment_album_downloads(song["album_id"])
            await db.db.users.update_one(
                {"_id": callback.from_user.id}, {"$inc": {"total_downloads": 1}}
            )
        except Exception:
            pass
        caption = await _build_caption(song)
        await callback.message.answer_audio(
            audio=song["file_id"],
            title=song["title"],
            caption=caption,
            parse_mode="HTML",
        )
        logging.info("Audio sent user=%s track=%s", callback.from_user.id, song_id)
        await _safe_answer(callback, "🎵 ပို့လိုက်ပါပြီ!")
    except Exception:
        logging.exception("song: handler failed")
        await _safe_answer(callback, "⚠️ အမှားဖြစ်သွားသည်။")


@router.callback_query(F.data.startswith("send_song:"))
async def send_chosen_song(callback: CallbackQuery):
    try:
        song_id = ObjectId(callback.data.split(":")[1])
        song = await db.get_song(song_id)
        if not song:
            await _safe_answer(callback, "❌ သီချင်းမတွေ့ပါ!")
            return
        try:
            await db.increment_song_downloads(song_id)
            await db.increment_album_downloads(song["album_id"])
            await db.db.users.update_one(
                {"_id": callback.from_user.id}, {"$inc": {"total_downloads": 1}}
            )
        except Exception:
            pass
        caption = await _build_caption(song)
        await callback.message.answer_audio(
            audio=song["file_id"],
            title=song["title"],
            caption=caption,
            parse_mode="HTML",
        )
        logging.info("Album audio sent user=%s track=%s", callback.from_user.id, song_id)
        await _safe_answer(callback, "🎵 ပို့လိုက်ပါပြီ!")
    except Exception:
        logging.exception("send_song: handler failed")
        await _safe_answer(callback, "⚠️ အမှားဖြစ်သွားသည်။")


# ---------------- Album download list ----------------

@router.callback_query(F.data.startswith("dl_album:"))
async def download_album(callback: CallbackQuery):
    try:
        album_id = ObjectId(callback.data.split(":")[1])
        songs = await db.get_songs(album_id)
        if not songs:
            await _safe_answer(callback, "🎵 သီချင်းမရှိပါ!")
            return
        await db.increment_album_downloads(album_id)
        await callback.message.answer(
            f"📀 <b>အယ်လ်ဘမ်ထဲမှ သီချင်းများ ({len(songs)})</b>\n\n"
            "ပို့စေချင်သော သီချင်းကို ရွေးပါ:",
            parse_mode="HTML",
            reply_markup=album_songs_to_send(album_id, songs),
        )
        await _safe_answer(callback, "📀 စာရင်း")
    except Exception:
        logging.exception("dl_album failed")
        await _safe_answer(callback, "⚠️ အမှားဖြစ်သွားသည်။")


@router.callback_query(F.data == "search")
async def search_prompt(callback: CallbackQuery):
    from handlers.search import SEARCHING_USERS
    SEARCHING_USERS.add(callback.from_user.id)
    await callback.message.answer(
        "🔍 <b>ရှာဖွေရန် အဆိုတော် သို့မဟုတ် သီချင်းအမည် ရိုက်ထည့်ပါ:</b>\n\n"
        "ဥပမာ: <code>ချစ်</code> သို့မဟုတ် <code>အိုင်</code>",
        parse_mode="HTML",
    )
    await _safe_answer(callback, "🔍 ရှာဖွေရမည့် အမည် ရိုက်ပါ")