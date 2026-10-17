import html
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from bson import ObjectId
from keyboards.inline import album_songs_to_send
from utils.i18n import t, get_lang

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
    lang = await get_lang(callback.from_user.id)
    try:
        song_id = ObjectId(callback.data.split(":")[1])
        song = await db.get_song(song_id)
        if not song:
            await _safe_answer(callback, t("song_not_found", lang))
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
        await _safe_answer(callback, t("sent_ok", lang))
    except Exception:
        logging.exception("song: handler failed")
        await _safe_answer(callback, t("error_generic", lang))


@router.callback_query(F.data.startswith("send_song:"))
async def send_chosen_song(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    try:
        song_id = ObjectId(callback.data.split(":")[1])
        song = await db.get_song(song_id)
        if not song:
            await _safe_answer(callback, t("song_not_found", lang))
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
        await _safe_answer(callback, t("sent_ok", lang))
    except Exception:
        logging.exception("send_song: handler failed")
        await _safe_answer(callback, t("error_generic", lang))


# ---------------- Album download list ----------------

@router.callback_query(F.data.startswith("dl_album:"))
async def download_album(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    try:
        album_id = ObjectId(callback.data.split(":")[1])
        songs = await db.get_songs(album_id)
        if not songs:
            await _safe_answer(callback, t("songs_empty", lang))
            return
        await db.increment_album_downloads(album_id)
        await callback.message.answer(
            t("dl_album_header", lang, n=len(songs)),
            parse_mode="HTML",
            reply_markup=album_songs_to_send(album_id, songs, lang),
        )
        await _safe_answer(callback, "📀")
    except Exception:
        logging.exception("dl_album failed")
        await _safe_answer(callback, t("error_generic", lang))


@router.callback_query(F.data == "cancel")
async def close_menu(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    try:
        await callback.message.delete()
    except Exception:
        await callback.answer()
    else:
        await callback.answer(t("closed", lang))


@router.callback_query(F.data == "search")
async def search_prompt(callback: CallbackQuery):
    from handlers.search import SEARCHING_USERS
    SEARCHING_USERS.add(callback.from_user.id)
    lang = await get_lang(callback.from_user.id)
    await callback.message.answer(t("search_prompt", lang), parse_mode="HTML")
    await _safe_answer(callback, t("m_search", lang))
