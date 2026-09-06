from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
import logging
import html
from database import db
from config import ADMIN_IDS, CHANNEL_ID
from bson import ObjectId
from keyboards.inline import (
    admin_main_kb,
    admin_delete_menu_kb,
    album_add_cat_kb,
    album_added_kb,
    song_added_kb,
    adding_songs_kb,
    categories_kb,
    albums_kb,
    back_to_cats_kb,
)

router = Router()
admin_router = router  # all callbacks gated by is_admin check


class AdminStates(StatesGroup):
    waiting_cat_name = State()
    waiting_cat_desc = State()
    waiting_album_name = State()
    waiting_album_artist = State()
    waiting_album_cat = State()
    waiting_album_cover = State()
    adding_songs = State()


async def is_admin(user_id) -> bool:
    return user_id in ADMIN_IDS


# ---------------- Admin menu ----------------
@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    current = callback.message
    from utils.formatters import get_admin_panel_text
    await current.edit_text(get_admin_panel_text(), parse_mode="HTML", reply_markup=admin_main_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_add_cat")
async def admin_add_cat(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    await state.set_state(AdminStates.waiting_cat_name)
    await callback.message.answer("➕ <b>အမျိုးအစား အမည် ရိုက်ထည့်ပါ:</b>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_add_album")
async def admin_add_album(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    cats = await db.get_categories()
    if not cats:
        await callback.answer("⚠️ ဦးစွာ အမျိုးအစားတစ်ခု ထည့်ပါ!")
        return
    await state.set_state(AdminStates.waiting_album_cat)
    await callback.message.answer(
        "📀 <b>အယ်လ်ဘမ် ထည့်မည့် အမျိုးအစား ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=album_add_cat_kb(cats),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_song")
async def admin_add_song(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    cats = await db.get_categories()
    if not cats:
        await callback.answer("⚠️ အရင်ဆုံး အမျိုးအစားတစ်ခု ထည့်ပါ!")
        return
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(text=f"🎵 {cat['name']}", callback_data=f"addsong_cat:{cat['_id']}")
    builder.button(text="🔙 နောက်သို့", callback_data="admin_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "🎵 <b>သီချင်းထည့်မည့် အမျိုးအစား ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addsong_cat:"))
async def addsong_cat(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    cat_id = ObjectId(callback.data.split(":")[1])
    albums = await db.get_albums(cat_id)
    if not albums:
        await callback.answer("⚠️ ဤအမျိုးအစားတွင် အယ်လ်ဘမ် မရှိပါ!")
        return
    builder = InlineKeyboardBuilder()
    for album in albums:
        builder.button(text=f"📀 {album['name']}", callback_data=f"addsong_album:{album['_id']}")
    builder.button(text="🔙 နောက်သို့", callback_data="admin_add_song")
    builder.adjust(1)
    await callback.message.edit_text(
        "📀 <b>သီချင်းထည့်မည့် အယ်လ်ဘမ် ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addsong_album:"))
async def addsong_album(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    album_id = ObjectId(callback.data.split(":")[1])
    await _begin_song_batch(callback.message, state, album_id)
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    stats = await db.get_stats()
    text = (
        "📊 <b>စာရင်းဇယား:</b>\n\n"
        f"🎵 သီချင်းများ: <b>{stats['songs']}</b>\n"
        f"📀 အယ်လ်ဘမ်များ: <b>{stats['albums']}</b>\n"
        f"👥 အသုံးပြုသူများ: <b>{stats['users']}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_cats_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_delete_menu")
async def admin_delete_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    cats = await db.get_categories()
    if not cats:
        await callback.answer("⚠️ ဖျက်ရန် အမျိုးအစား မရှိပါ!")
        return
    await callback.message.edit_text(
        "🗑 <b>ဖျက်မည့် အမျိုးအစား ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=admin_delete_menu_kb(cats),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_cat:"))
async def delete_category(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    cat_id = ObjectId(callback.data.split(":")[1])
    await db.delete_category(cat_id)
    await callback.answer("🗑 အမျိုးအစား ဖျက်ပြီးပါပြီ!")
    cats = await db.get_categories()
    await callback.message.edit_text(
        "🗑 <b>ဖျက်မည့် အမျိုးအစား ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=admin_delete_menu_kb(cats),
    )


# ---------------- FSM states ----------------

@router.message(AdminStates.waiting_cat_name)
async def receive_cat_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(cat_name=name)
    await state.set_state(AdminStates.waiting_cat_desc)
    await message.answer("📝 <b>ဖော်ပြချက် ရိုက်ထည့်ပါ (မလိုရင် /skip):</b>", parse_mode="HTML")


@router.message(AdminStates.waiting_cat_desc, F.text == "/skip")
async def skip_cat_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_category(data["cat_name"], "")
    await state.clear()
    await message.answer("✅ <b>အမျိုးအစား ထည့်ပြီးပါပြီ!</b>", parse_mode="HTML", reply_markup=admin_main_kb())


@router.message(AdminStates.waiting_cat_desc)
async def receive_cat_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    data = await state.get_data()
    await db.add_category(data["cat_name"], desc)
    await state.clear()
    await message.answer("✅ <b>အမျိုးအစား ထည့်ပြီးပါပြီ!</b>", parse_mode="HTML", reply_markup=admin_main_kb())


@router.callback_query(AdminStates.waiting_album_cat, F.data.startswith("albadd_cat:"))
async def choose_album_cat(callback: CallbackQuery, state: FSMContext):
    cat_id = ObjectId(callback.data.split(":")[1])
    await state.update_data(album_cat_id=cat_id)
    await state.set_state(AdminStates.waiting_album_name)
    await callback.message.answer("📀 <b>အယ်လ်ဘမ် အမည် ရိုက်ထည့်ပါ:</b>", parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_album_name)
async def receive_album_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(album_name=name)
    await state.set_state(AdminStates.waiting_album_artist)
    await message.answer("🎤 <b>အနုပညာရှင် အမည် ရိုက်ထည့်ပါ (မလိုရင် /skip):</b>", parse_mode="HTML")


@router.message(AdminStates.waiting_album_artist, F.text == "/skip")
async def skip_album_artist(message: Message, state: FSMContext):
    await state.update_data(album_artist="")
    await state.set_state(AdminStates.waiting_album_cover)
    await message.answer("🖼 <b>အယ်လ်ဘမ် ကာဗာပုံ ပို့ပါ (မလိုရင် /skip):</b>", parse_mode="HTML")


@router.message(AdminStates.waiting_album_artist)
async def receive_album_artist(message: Message, state: FSMContext):
    await state.update_data(album_artist=message.text.strip())
    await state.set_state(AdminStates.waiting_album_cover)
    await message.answer("🖼 <b>အယ်လ်ဘမ် ကာဗာပုံ ပို့ပါ (မလိုရင် /skip):</b>", parse_mode="HTML")


@router.message(AdminStates.waiting_album_cover, F.photo)
async def receive_album_cover(message: Message, state: FSMContext):
    cover = message.photo[-1].file_id
    await _finish_add_album(message, state, cover)


@router.message(AdminStates.waiting_album_cover, F.text == "/skip")
async def skip_album_cover(message: Message, state: FSMContext):
    await _finish_add_album(message, state, "")


@router.message(AdminStates.waiting_album_cover)
async def album_cover_wrong_type(message: Message):
    await message.answer("🖼 <b>ကာဗာအတွက် ပုံ ပို့ပါ သို့မဟုတ် /skip နှိပ်ပါ:</b>", parse_mode="HTML")


async def _finish_add_album(message: Message, state: FSMContext, cover=""):
    data = await state.get_data()
    result = await db.add_album(
        data.get("album_name", ""),
        data.get("album_artist", ""),
        data.get("album_cat_id"),
        cover,
    )
    album_id = result.inserted_id
    await state.clear()

    name = data.get("album_name", "")
    artist = data.get("album_artist", "")
    text = f"✅ <b>အယ်လ်ဘမ် ထည့်ပြီးပါပြီ!</b>\n\n"
    text += f"📀 <b>{html.escape(name)}</b>\n"
    if artist:
        text += f"🎤 {html.escape(artist)}\n"
    text += "\nအခု သီချင်းများ ထည့်နိုင်ပါပြီ 👇"
    await message.answer(text, parse_mode="HTML", reply_markup=album_added_kb(album_id))


# ---------------- Song upload (batch) ----------------

async def _begin_song_batch(message: Message, state: FSMContext, album_id):
    album = await db.get_album(album_id)
    album_name = album["name"] if album else ""
    await state.set_data({"song_album_id": album_id, "song_count": 0, "pending_title": None})
    await state.set_state(AdminStates.adding_songs)
    text = (
        f"🎵 <b>သီချင်းများ ထည့်မည်</b>\n\n"
        f"📀 <b>{html.escape(album_name)}</b>\n\n"
        "1️⃣ ချန်နယ် (သို့) အခြားနေရာမှ အသံဖိုင်များကို forward/ပို့ပါ — "
        "တစ်ခါတည်း အများကြီး ပို့လို့ရပါသည်\n"
        "2️⃣ အားလုံး ပို့ပြီးရင် \"✅ ပြီးပါပြီ\" ခလုတ် နှိပ်ပါ\n\n"
        "💡 သီချင်းတစ်ပုဒ်ချင်းစီ နာမည် သတ်မှတ်ချင်ရင် ဖိုင်မပို့ခင် "
        "နာမည် ဦးစွာ ရိုက်ထည့်နိုင်ပါသည် (မထည့်ရင် ဖိုင်မှ metadata အတိုင်း ယူပါမည်)"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=adding_songs_kb(album_id))


@router.callback_query(F.data.startswith("add_song:"))
async def start_song_upload(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    album_id = ObjectId(callback.data.split(":")[1])
    await _begin_song_batch(callback.message, state, album_id)
    await callback.answer()


@router.message(AdminStates.adding_songs, F.audio | F.document)
async def add_batch_song(message: Message, state: FSMContext):
    data = await state.get_data()
    album_id = data["song_album_id"]
    custom_title = data.get("pending_title") or ""

    if message.audio:
        file_id = message.audio.file_id
        file_size = message.audio.file_size or 0
        duration = message.audio.duration or 0
        auto_title = message.audio.title or ""
    else:
        if "audio" not in (message.document.mime_type or ""):
            await message.answer("⚠️ <b>အသံဖိုင် သာ ပို့နိုင်ပါသည်။</b>", parse_mode="HTML")
            return
        file_id = message.document.file_id
        file_size = message.document.file_size or 0
        duration = 0
        auto_title = message.document.file_name or ""

    title = custom_title or auto_title or "အမည်မသိ"
    if not custom_title and title.lower().endswith((".mp3", ".m4a", ".ogg", ".wav")):
        title = title.rsplit(".", 1)[0]

    await db.add_song(title, album_id, file_id, file_size, duration)
    count = data.get("song_count", 0) + 1
    await state.update_data(song_count=count, pending_title=None)

    await message.answer(
        f"📥 <b>သီချင်း ({count})</b> ✅\n\n"
        f"🎵 <b>{html.escape(title)}</b>\n"
        "ထပ်ပို့ပါ — အားလုံးပြီးရင် \"✅ ပြီးပါပြီ\" နှိပ်ပါ 👇",
        parse_mode="HTML",
        reply_markup=adding_songs_kb(album_id),
    )


@router.message(AdminStates.adding_songs, F.text)
async def set_batch_song_title(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        return
    data = await state.get_data()
    await state.update_data(pending_title=message.text.strip())
    await message.answer(
        f"🎵 နာမည် သတ်မှတ်ပြီ — <b>{html.escape(message.text.strip())}</b>\n"
        "အခု သီချင်းဖိုင် ပို့ပါ 👇",
        parse_mode="HTML",
        reply_markup=adding_songs_kb(data["song_album_id"]),
    )


@router.message(AdminStates.adding_songs)
async def batch_add_wrong_type(message: Message):
    await message.answer(
        "⚠️ <b>အသံဖိုင် (.mp3) ပို့ပါ</b> သို့မဟုတ် \"✅ ပြီးပါပြီ\" ခလုတ် နှိပ်ပါ။",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("finish_songs:"))
async def finish_batch(callback: CallbackQuery, state: FSMContext):
    album_id = ObjectId(callback.data.split(":")[1])
    data = await state.get_data()
    count = data.get("song_count", 0)
    album = await db.get_album(album_id)
    album_name = album["name"] if album else ""
    await state.clear()

    if count == 0:
        text = (
            "⚠️ <b>သီချင်း မထည့်ရသေးပါ!</b>\n\n"
            "အသံဖိုင်များ forward ပို့ပြီးမှ \"✅ ပြီးပါပြီ\" ခလုတ် နှိပ်ပါ။"
        )
        kb = album_added_kb(album_id)
    else:
        text = (
            f"✅ <b>ပြီးပါပြီ!</b>\n\n"
            f"📀 {html.escape(album_name)}\n"
            f"🎵 ထည့်ပြီး သီချင်း: <b>{count}</b> ပုဒ်\n\n"
            "🎧 User များ အခု album ထဲမှ နားဆင် / ဒေါင်းလုဒ်လို့ ရပါပြီ!"
        )
        kb = song_added_kb(album_id)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "cancel_batch")
async def cancel_batch(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "❌ <b>ထည့်ခြင်း ရပ်လိုက်ပါပြီ</b>\n\n"
        "(ထည့်ပြီးသား သီချင်းများမှာ သိမ်းထားပြီးသား ဖြစ်ပါသည်)",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )
    await callback.answer()
