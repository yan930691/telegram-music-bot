from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
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
    waiting_song_title = State()
    waiting_song_album = State()
    waiting_song_file = State()


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
        reply_markup=admin_delete_menu_kb(cats),  # reuse for selection, custom
    )
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


@router.callback_query(AdminStates.waiting_album_cat)
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
    data = await state.get_data()
    await db.add_album(data["album_name"], "", data["album_cat_id"])
    await state.clear()
    await message.answer("✅ <b>အယ်လ်ဘမ် ထည့်ပြီးပါပြီ!</b>", parse_mode="HTML", reply_markup=admin_main_kb())


@router.message(AdminStates.waiting_album_artist)
async def receive_album_artist(message: Message, state: FSMContext):
    artist = message.text.strip()
    data = await state.get_data()
    await db.add_album(data["album_name"], artist, data["album_cat_id"])
    await state.clear()
    await message.answer("✅ <b>အယ်လ်ဘမ် ထည့်ပြီးပါပြီ!</b>", parse_mode="HTML", reply_markup=admin_main_kb())


# ---------------- Song upload ----------------

@router.callback_query(F.data.startswith("add_song:"))
async def start_song_upload(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    album_id = ObjectId(callback.data.split(":")[1])
    await state.update_data(song_album_id=album_id)
    await state.set_state(AdminStates.waiting_song_title)
    await callback.message.answer("🎵 <b>သီချင်းအမည် ရိုက်ထည့်ပါ:</b>", parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_song_title)
async def receive_song_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(song_title=title)
    await state.set_state(AdminStates.waiting_song_file)
    await message.answer(
        "📤 <b>အသံဖိုင် (.mp3) ကို ပို့ပါ:</b>\n\n"
        "သီချင်းဖိုင်ကို chat ထဲ ပို့ပေးပါ။",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_song_file, F.audio | F.document)
async def receive_song_file(message: Message, state: FSMContext):
    data = await state.get_data()

    # Extract file_id
    if message.audio:
        file_id = message.audio.file_id
        file_size = message.audio.file_size or 0
        duration = message.audio.duration or 0
        if not data.get("song_title") and message.audio.title:
            await state.update_data(song_title=message.audio.title)
            data["song_title"] = message.audio.title
    elif message.document:
        file_id = message.document.file_id
        file_size = message.document.file_size or 0
        duration = 0
        mime = message.document.mime_type or ""
        if "audio" not in mime:
            await message.answer("⚠️ <b>အသံဖိုင် သာ ပို့နိုင်ပါသည်။</b>", parse_mode="HTML")
            return
    else:
        await message.answer("⚠️ အသံဖိုင် ပို့ပါ!")
        return

    title = data.get("song_title", "အမည်မသိ")
    album_id = data["song_album_id"]
    await db.add_song(
        title,
        album_id,
        file_id,
        file_size,
        duration,
    )
    await state.clear()
    await message.answer(
        f"✅ <b>သီချင်းထည့်ပြီးပါပြီ!</b>\n\n"
        f"🎵 {title}",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )

    # Announce new release to channel
    album = await db.get_album(album_id)
    album_name = album["name"] if album else ""
    if CHANNEL_ID:
        try:
            await message.bot.send_audio(
                chat_id=CHANNEL_ID,
                audio=file_id,
                title=title,
                caption=(
                    "🎵 <b>သီချင်းအသစ် ထွက်ရှိပါပြီ!</b>\n\n"
                    f"🎧 <b>{html.escape(title)}</b>\n"
                    f"📀 {html.escape(album_name)}\n\n"
                    "🤖 Bot မှ ရယူလိုပါက အောက်ပါ bot သို့ ဝင်ရောက်ပါ"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logging.warning(f"Channel announcement failed: {e}")


@router.message(AdminStates.waiting_song_file)
async def receive_song_file_wrong_type(message: Message):
    await message.answer("⚠️ <b>အသံဖိုင် (.mp3) ကို ပို့ပါ!</b>", parse_mode="HTML")
