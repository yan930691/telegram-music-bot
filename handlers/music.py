import html
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from bson import ObjectId
from keyboards.inline import album_songs_to_send, player_kb, songs_kb

router = Router()

# Per-user music player state
PLAYERS = {}


def _set_player(user_id, album_id, album_name, songs, index=0):
    PLAYERS[user_id] = {
        "album_id": album_id,
        "album_name": album_name,
        "songs": songs,
        "index": index,
        "paused": False,
    }
    return PLAYERS[user_id]


async def _safe_answer(callback: CallbackQuery, text: str):
    try:
        await callback.answer(text)
    except Exception:
        pass


async def _remove_player_kb(callback: CallbackQuery):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def _play(callback: CallbackQuery, user_id, remove=True):
    """Send the current playlist track with the player controls attached."""
    pl = PLAYERS.get(user_id)
    if not pl or not pl.get("songs"):
        await _safe_answer(callback, "⚠️ ပထမဆုံး သီချင်းရွေး ပါ!")
        return

    try:
        songs = pl["songs"]
        idx = pl["index"] % len(songs)
        pl["index"] = idx
        pl["paused"] = False
        song = songs[idx]
        song_title = song["title"]
        album_id = pl["album_id"]

        if remove:
            await _remove_player_kb(callback)

        try:
            await db.increment_song_downloads(song["_id"])
            await db.increment_album_downloads(album_id)
            await db.db.users.update_one(
                {"_id": user_id}, {"$inc": {"total_downloads": 1}}
            )
        except Exception:
            pass

        caption = (
            f"🎧 <b>ဂီတ Player</b>\n\n"
            f"🎵 <b>{html.escape(song_title)}</b>\n"
            f"📀 {html.escape(pl.get('album_name', ''))}\n\n"
            f"🎚 {idx + 1}/{len(songs)}"
        )
        await callback.message.answer_audio(
            audio=song["file_id"],
            title=song_title,
            caption=caption,
            parse_mode="HTML",
            reply_markup=player_kb(str(album_id), idx + 1, len(songs), paused=False),
        )
        logging.info("Player play user=%s track=%s (%s/%s)", user_id, song["_id"], idx + 1, len(songs))
        await _safe_answer(callback, f"▶️ {song_title[:40]}")
    except Exception as e:
        logging.exception("Player play failed user=%s", user_id)
        await _safe_answer(callback, "⚠️ အမှားဖြစ်သွားသည်။ ခဏအောင့်ပြီး ပြန်နှိပ်ပါ။")


# ---------------- Start player ----------------

@router.callback_query(F.data.startswith("p:start:"))
async def player_start(callback: CallbackQuery):
    try:
        album_id = ObjectId(callback.data.split(":")[2])
        songs = await db.get_songs(album_id)
        if not songs:
            await _safe_answer(callback, "🎵 သီချင်းမရှိပါ!")
            return
        album = await db.get_album(album_id)
        user_id = callback.from_user.id
        _set_player(user_id, album_id, album["name"] if album else "", songs, 0)
        await _play(callback, user_id, remove=False)
    except Exception:
        logging.exception("Player start failed")
        await _safe_answer(callback, "⚠️ အမှားဖြစ်သွားသည်။")


@router.callback_query(F.data.startswith("song:"))
async def send_single_song(callback: CallbackQuery):
    try:
        song_id = ObjectId(callback.data.split(":")[1])
        song = await db.get_song(song_id)
        if not song:
            await _safe_answer(callback, "❌ သီချင်းမတွေ့ပါ!")
            return
        album = await db.get_album(song["album_id"])
        songs = await db.get_songs(song["album_id"])
        idx = next((i for i, s in enumerate(songs) if s["_id"] == song_id), 0)
        user_id = callback.from_user.id
        _set_player(user_id, song["album_id"], album["name"] if album else "", songs, idx)
        await _play(callback, user_id, remove=False)
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
        album = await db.get_album(song["album_id"])
        songs = await db.get_songs(song["album_id"])
        idx = next((i for i, s in enumerate(songs) if s["_id"] == song_id), 0)
        user_id = callback.from_user.id
        _set_player(user_id, song["album_id"], album["name"] if album else "", songs, idx)
        await _play(callback, user_id, remove=False)
    except Exception:
        logging.exception("send_song: handler failed")
        await _safe_answer(callback, "⚠️ အမှားဖြစ်သွားသည်။")


# ---------------- Player controls ----------------

@router.callback_query(F.data == "p:prev")
async def player_prev(callback: CallbackQuery):
    user_id = callback.from_user.id
    pl = PLAYERS.get(user_id)
    if not pl or not pl.get("songs"):
        await _safe_answer(callback, "⚠️ ပထမဆုံး သီချင်းရွေး ပါ!")
        return
    pl["index"] = (pl["index"] - 1) % len(pl["songs"])
    logging.info("Player prev user=%s index=%s", user_id, pl["index"])
    await _play(callback, user_id, remove=True)


@router.callback_query(F.data == "p:next")
async def player_next(callback: CallbackQuery):
    user_id = callback.from_user.id
    pl = PLAYERS.get(user_id)
    if not pl or not pl.get("songs"):
        await _safe_answer(callback, "⚠️ ပထမဆုံး သီချင်းရွေး ပါ!")
        return
    pl["index"] = (pl["index"] + 1) % len(pl["songs"])
    logging.info("Player next user=%s index=%s", user_id, pl["index"])
    await _play(callback, user_id, remove=True)


@router.callback_query(F.data == "p:toggle")
async def player_toggle(callback: CallbackQuery):
    user_id = callback.from_user.id
    pl = PLAYERS.get(user_id)
    if not pl or not pl.get("songs"):
        await _safe_answer(callback, "⚠️ ပထမဆုံး သီချင်းရွေး ပါ!")
        return

    if pl["paused"]:
        pl["paused"] = False
        logging.info("Player resume user=%s", user_id)
        await _play(callback, user_id, remove=False)
    else:
        pl["paused"] = True
        try:
            await callback.message.edit_reply_markup(
                reply_markup=player_kb(
                    str(pl["album_id"]),
                    pl["index"] + 1,
                    len(pl["songs"]),
                    paused=True,
                )
            )
        except Exception:
            pass
        await _safe_answer(callback, "⏸ ခဏရပ်ထားသည် — ▶️ နှိပ်လျှင် ပြန်ဖွင့်ပါမည်")


@router.callback_query(F.data == "p:list")
async def player_list(callback: CallbackQuery):
    pl = PLAYERS.get(callback.from_user.id)
    if not pl or not pl.get("songs"):
        await _safe_answer(callback, "⚠️ ပထမဆုံး သီချင်းရွေး ပါ!")
        return
    try:
        await callback.message.edit_caption(
            caption=(
                f"🎵 <b>{html.escape(pl.get('album_name', ''))}</b> — သီချင်းစာရင်း ({len(pl['songs'])})\n\n"
                f"▶️ နားဆင်နေသည်: <b>{html.escape(pl['songs'][pl['index']]['title'])}</b>\n\n"
                "သီချင်းရွေးရန် နှိပ်ပါ:"
            ),
            parse_mode="HTML",
            reply_markup=songs_kb(pl["songs"], pl["album_id"]),
        )
        await _safe_answer(callback, "🎵 စာရင်း")
    except Exception:
        logging.exception("Player list failed")
        await _safe_answer(callback, "⚠️ စာရင်းဖွင့်မရပါ။")


@router.callback_query(F.data == "p:close")
async def player_close(callback: CallbackQuery):
    PLAYERS.pop(callback.from_user.id, None)
    await _remove_player_kb(callback)
    await _safe_answer(callback, "❌ Player ပိတ်လိုက်ပါပြီ!")


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
        "🔍 <b>ရှာဖွေရန် သီချင်းအမည် ရိုက်ထည့်ပါ:</b>\n\n"
        "ဥပမာ: <code>ချစ်</code>",
        parse_mode="HTML",
    )
    await _safe_answer(callback, "🔍 ရှာဖွေရမည့် အမည် ရိုက်ပါ")