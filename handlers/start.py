from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from utils.formatters import get_welcome_text, get_help_text, get_admin_panel_text
from keyboards.inline import (
    main_menu_kb,
    categories_kb,
    category_actions_kb,
    albums_kb,
    album_actions_kb,
    songs_kb,
    admin_main_kb,
)
from database import db
from bson import ObjectId
from config import ADMIN_IDS

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name,
    )
    await message.answer(
        get_welcome_text(),
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(get_help_text(), parse_mode="HTML")


@router.message(Command("menu"))
async def menu_handler(message: Message):
    await message.answer("🎵 မီနူး:", parse_mode="HTML", reply_markup=main_menu_kb())


@router.message(Command("admin"))
async def admin_handler(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer(
            get_admin_panel_text(),
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
    else:
        await message.answer("❌ သင်သည် အက်ဒမင် မဟုတ်ပါ။")


# ---------------- Callbacks ----------------

@router.callback_query(F.data == "cats")
async def show_categories(callback: CallbackQuery):
    cats = await db.get_categories()
    if not cats:
        await callback.message.edit_text(
            "📂 အမျိုးအစားများ မရှိသေးပါ။",
            reply_markup=categories_kb([]),
        )
    else:
        await callback.message.edit_text(
            "📂 <b>အမျိုးအစားများ ရွေးချယ်ပါ:</b>",
            parse_mode="HTML",
            reply_markup=categories_kb(cats),
        )
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎵 မီနူး:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery):
    cat_id = ObjectId(callback.data.split(":")[1])
    cat = await db.get_category(cat_id)
    if not cat:
        await callback.answer("❌ အမျိုးအစား မတွေ့ပါ!")
        return
    is_admin = callback.from_user.id in ADMIN_IDS
    text = f"🎵 <b>{cat['name']}</b>\n\n"
    if cat.get("description"):
        text += f"📝 {cat['description']}\n\n"
    text += "အောက်ပါ လုပ်ဆောင်ချက်များ ရွေးချယ်ပါ:"
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=category_actions_kb(cat_id, is_admin),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("albums:"))
async def show_albums(callback: CallbackQuery):
    cat_id = ObjectId(callback.data.split(":")[1])
    albums = await db.get_albums(cat_id)
    if not albums:
        await callback.answer("📂 အယ်လ်ဘမ် မရှိသေးပါ!")
        return
    await callback.message.edit_text(
        "📀 <b>အယ်လ်ဘမ်များ:</b>",
        parse_mode="HTML",
        reply_markup=albums_kb(albums, cat_id),
    )
    await callback.answer()


@router.callback_query(F.data == "albums_back")
async def albums_back(callback: CallbackQuery):
    cats = await db.get_categories()
    await callback.message.edit_text(
        "📂 <b>အမျိုးအစားများ ရွေးချယ်ပါ:</b>",
        parse_mode="HTML",
        reply_markup=categories_kb(cats),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("album:"))
async def show_album(callback: CallbackQuery):
    album_id = ObjectId(callback.data.split(":")[1])
    album = await db.get_album(album_id)
    if not album:
        await callback.answer("❌ အယ်လ်ဘမ် မတွေ့ပါ!")
        return
    is_admin = callback.from_user.id in ADMIN_IDS
    text = f"📀 <b>{album['name']}</b>\n"
    if album.get("artist"):
        text += f"🎤 {album['artist']}\n"
    text += f"📥 ဒေါင်းလုဒ်: {album.get('downloads', 0)}\n\n"
    text += "လုပ်ဆောင်ချက် ရွေးချယ်ပါ:"
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=album_actions_kb(album_id, is_admin),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("songs:"))
async def show_songs(callback: CallbackQuery):
    album_id = ObjectId(callback.data.split(":")[1])
    songs = await db.get_songs(album_id)
    if not songs:
        await callback.answer("🎵 သီချင်းမရှိသေးပါ!")
        return
    await callback.message.edit_text(
        f"🎵 <b>သီချင်းများ ({len(songs)}):</b>",
        parse_mode="HTML",
        reply_markup=songs_kb(songs, album_id),
    )
    await callback.answer()


@router.callback_query(F.data == "songs_all")
async def show_all_songs(callback: CallbackQuery):
    from bson.objectid import ObjectId as OID
    import re

    # Get all albums grouped
    cats = await db.get_categories()
    if not cats:
        await callback.answer("📂 အမျိုးအစား မရှိသေးပါ!")
        return
    await callback.message.edit_text(
        "🎵 <b>အမျိုးအစားရွေးပြီး သီချင်းများ ကြည့်နိုင်ပါသည်:</b>",
        parse_mode="HTML",
        reply_markup=categories_kb(cats),
    )
    await callback.answer()


@router.callback_query(F.data == "popular")
async def show_popular(callback: CallbackQuery):
    from keyboards.inline import popular_songs_kb
    songs = await db.db.songs.find().sort("downloads", -1).limit(10).to_list(length=10)
    if not songs:
        await callback.answer("🔥 လူကြိုက်များသော သီချင်း မရှိသေးပါ!")
        return
    await callback.message.edit_text(
        "🔥 <b>လူကြိုက်များသော သီချင်းများ (ထိပ်တန်း 10):</b>",
        parse_mode="HTML",
        reply_markup=popular_songs_kb(songs),
    )
    await callback.answer()
