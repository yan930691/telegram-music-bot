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
from config import ADMIN_IDS, BUILD_VERSION

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
        reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS),
    )


@router.message(Command("version"))
async def version_handler(message: Message):
    if message.from_user.id in ADMIN_IDS:
        stats = await db.get_stats()
        await message.answer(
            f"⚙️ <b>Bot Build</b>\n\n"
            f"🆕 Version: <code>{BUILD_VERSION}</code>\n"
            f"🎵 သီချင်း: {stats['songs']}\n"
            f"📀 အယ်လ်ဘမ်: {stats['albums']}\n"
            f"👥 အသုံးပြုသူ: {stats['users']}",
            parse_mode="HTML",
        )
    else:
        await message.answer("❌ သင်သည် အက်ဒမင် မဟုတ်ပါ။")


@router.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(get_help_text(), parse_mode="HTML")


@router.message(Command("menu"))
async def menu_handler(message: Message):
    await message.answer("🎵 မီနူး:", parse_mode="HTML", reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS))


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
            "📂 သီချင်းအမျိုးအစားများ မရှိသေးပါ။",
            reply_markup=categories_kb([]),
        )
    else:
        await callback.message.edit_text(
            "📂 <b>သီချင်းအမျိုးအစားများ ရွေးချယ်ပါ:</b>",
            parse_mode="HTML",
            reply_markup=categories_kb(cats),
        )
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎵 မီနူး:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(callback.from_user.id in ADMIN_IDS),
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
        "📂 <b>သီချင်းအမျိုးအစားများ ရွေးချယ်ပါ:</b>",
        parse_mode="HTML",
        reply_markup=categories_kb(cats),
    )
    await callback.answer()


@router.callback_query(F.data == "artists_all")
async def show_artists(callback: CallbackQuery):
    from keyboards.inline import artists_kb
    artists = await db.get_all_artists()
    if not artists:
        await callback.answer("🎤 အနုပညာရှင် မရှိသေးပါ!")
        return
    await callback.message.edit_text(
        "🎤 <b>အနုပညာရှင်များ ({0}):</b>\n\n"
        "အဆိုတော် ရွေးပါက ၎င်း၏ အယ်လ်ဘမ်များ ပြပါမည်:".format(len(artists)),
        parse_mode="HTML",
        reply_markup=artists_kb(artists),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("artist:"))
async def show_artist(callback: CallbackQuery):
    from keyboards.inline import artist_albums_kb
    artist_id = ObjectId(callback.data.split(":")[1])
    artist = await db.get_artist(artist_id)
    if not artist:
        await callback.answer("❌ အနုပညာရှင် မတွေ့ပါ!")
        return
    albums = await db.get_artist_albums(artist_id)
    if not albums:
        await callback.answer("📀 ဤအနုပညာရှင်အတွက် အယ်လ်ဘမ် မရှိသေးပါ!")
        return
    await callback.message.edit_text(
        f"🎤 <b>{artist['name']}</b>\n"
        f"📀 အယ်လ်ဘမ်: {len(albums)}\n\n"
        "အယ်လ်ဘမ် ရွေးပါ:",
        parse_mode="HTML",
        reply_markup=artist_albums_kb(albums, artist_id),
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

    # Show cover as a separate photo (NOT as the button message).
    # The buttons stay on a text message so every button works.
    if album.get("cover"):
        try:
            await callback.message.answer_photo(
                photo=album["cover"],
                caption=f"📀 <b>{album['name']}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

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
        "🎵 <b>သီချင်းအမျိုးအစားရွေးပြီး သီချင်းများ ကြည့်နိုင်ပါသည်:</b>",
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


@router.callback_query(F.data == "songs_new")
async def show_new_songs(callback: CallbackQuery):
    from keyboards.inline import search_results_kb
    songs = await db.get_latest_songs(10)
    if not songs:
        await callback.answer("🆕 ထည့်သွင်းထားသော သီချင်း မရှိသေးပါ!")
        return
    await callback.message.edit_text(
        "🆕 <b>အသစ်ထည့်ထားသော သီချင်းများ (နောက်ဆုံး 10):</b>",
        parse_mode="HTML",
        reply_markup=search_results_kb(songs),
    )
    await callback.answer()
