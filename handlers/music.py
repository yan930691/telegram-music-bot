from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from database import db
from config import ADMIN_IDS
from bson import ObjectId
from keyboards.inline import search_results_kb, album_songs_to_send
from datetime import datetime

router = Router()


@router.callback_query(F.data.startswith("song:"))
async def send_single_song(callback: CallbackQuery):
    song_id = ObjectId(callback.data.split(":")[1])
    song = await db.get_song(song_id)
    if not song:
        await callback.answer("❌ သီချင်းမတွေ့ပါ!")
        return

    # Increment counters
    await db.increment_song_downloads(song_id)
    await db.increment_album_downloads(song["album_id"])
    act_user = callback.from_user.id
    await db.db.users.update_one({"_id": act_user}, {"$inc": {"total_downloads": 1}})

    await callback.message.answer_audio(
        audio=song["file_id"],
        title=song["title"],
        caption=f"🎵 {song['title']}\n\nကျေးဇူးပြု၍ 🎧 နားဆင်ပါ!",
        parse_mode="HTML",
    )
    await callback.answer("🎵 သီချင်းပို့ပေးပါပြီ!")


@router.callback_query(F.data.startswith("dl_album:"))
async def download_album(callback: CallbackQuery):
    album_id = ObjectId(callback.data.split(":")[1])
    songs = await db.get_songs(album_id)
    if not songs:
        await callback.answer("🎵 သီချင်းမရှိပါ!")
        return
    await db.increment_album_downloads(album_id)
    # Ask user which songs to send (avoid flooding)
    await callback.message.answer(
        f"📀 <b>အယ်လ်ဘမ်ထဲမှ သီချင်းများ ({len(songs)})</b>\n\n"
        "ပို့စေချင်သော သီချင်းကို ရွေးပါ:",
        parse_mode="HTML",
        reply_markup=album_songs_to_send(album_id, songs),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("send_song:"))
async def send_chosen_song(callback: CallbackQuery):
    song_id = ObjectId(callback.data.split(":")[1])
    song = await db.get_song(song_id)
    if not song:
        await callback.answer("❌ သီချင်းမတွေ့ပါ!")
        return
    await db.increment_song_downloads(song_id)
    await callback.message.answer_audio(
        audio=song["file_id"],
        title=song["title"],
        caption=f"🎵 {song['title']}\n\nကျေးဇူးပြု၍ 🎧 နားဆင်ပါ!",
        parse_mode="HTML",
    )
    await callback.answer("🎵 သီချင်းပို့ပေးပါပြီ!")


@router.callback_query(F.data == "search")
async def search_prompt(callback: CallbackQuery):
    from handlers.search import SEARCHING_USERS
    SEARCHING_USERS.add(callback.from_user.id)
    await callback.message.answer(
        "🔍 <b>ရှာဖွေရန် သီချင်းအမည် ရိုက်ထည့်ပါ:</b>\n\n"
        "ဥပမာ: <code>ချစ်</code>",
        parse_mode="HTML",
    )
    await callback.answer("🔍 ရှာဖွေရမည့် အမည် ရိုက်ပါ")
