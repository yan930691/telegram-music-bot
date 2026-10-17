from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from utils.formatters import get_welcome_text, get_help_text, get_admin_panel_text
from utils.i18n import t, get_lang, set_lang, LANG_NAMES
from keyboards.inline import (
    main_menu_kb,
    categories_kb,
    category_actions_kb,
    albums_kb,
    album_actions_kb,
    songs_kb,
    admin_main_kb,
    settings_kb,
)
from database import db
from bson import ObjectId
from config import ADMIN_IDS, BUILD_VERSION

router = Router()

_bot_username = None


async def _get_bot_username(bot):
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username or "this_bot"
    return _bot_username


@router.message(CommandStart())
async def start_handler(message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name,
    )
    lang = await get_lang(message.from_user.id)
    await message.answer(
        get_welcome_text(lang),
        parse_mode="HTML",
        reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS, lang),
    )


@router.message(Command("version"))
async def version_handler(message: Message):
    lang = await get_lang(message.from_user.id)
    if message.from_user.id in ADMIN_IDS:
        stats = await db.get_stats()
        await message.answer(
            t("version_info", lang, ver=BUILD_VERSION, songs=stats["songs"],
              albums=stats["albums"], users=stats["users"]),
            parse_mode="HTML",
        )
    else:
        await message.answer(t("not_admin_short", lang))


@router.message(Command("help"))
async def help_handler(message: Message):
    lang = await get_lang(message.from_user.id)
    username = await _get_bot_username(message.bot)
    await message.answer(get_help_text(lang, username), parse_mode="HTML")


@router.message(Command("menu"))
async def menu_handler(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(
        get_welcome_text(lang),
        parse_mode="HTML",
        reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS, lang),
    )


@router.message(Command("admin"))
async def admin_handler(message: Message):
    lang = await get_lang(message.from_user.id)
    if message.from_user.id in ADMIN_IDS:
        await message.answer(
            get_admin_panel_text(lang),
            parse_mode="HTML",
            reply_markup=admin_main_kb(lang),
        )
    else:
        await message.answer(t("not_admin_short", lang))


# ---------------- Callbacks ----------------

@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await callback.message.edit_text(
        t("settings_title", lang),
        parse_mode="HTML",
        reply_markup=settings_kb(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def choose_lang(callback: CallbackQuery):
    new_lang = callback.data.split(":", 1)[1]
    await set_lang(callback.from_user.id, new_lang)
    lang = await get_lang(callback.from_user.id)
    name = LANG_NAMES.get(lang, lang)
    await callback.message.edit_text(
        t("settings_title", lang) + "\n\n" + t("lang_set", lang, name=name),
        parse_mode="HTML",
        reply_markup=settings_kb(lang),
    )
    await callback.answer(t("lang_set", lang, name=name))


@router.callback_query(F.data == "cats")
async def show_categories(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    cats = await db.get_categories()
    if not cats:
        await callback.message.edit_text(
            t("cats_empty", lang),
            reply_markup=categories_kb([], lang),
        )
    else:
        await callback.message.edit_text(
            t("cats_header", lang),
            parse_mode="HTML",
            reply_markup=categories_kb(cats, lang),
        )
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await callback.message.edit_text(
        get_welcome_text(lang),
        parse_mode="HTML",
        reply_markup=main_menu_kb(callback.from_user.id in ADMIN_IDS, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    cat_id = ObjectId(callback.data.split(":")[1])
    cat = await db.get_category(cat_id)
    if not cat:
        await callback.answer(t("error_generic", lang))
        return
    is_admin = callback.from_user.id in ADMIN_IDS
    text = f"🎵 <b>{cat['name']}</b>\n\n"
    if cat.get("description"):
        text += f"📝 {cat['description']}\n\n"
    text += t("cat_actions_hint", lang)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=category_actions_kb(cat_id, is_admin, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("albums:"))
async def show_albums(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    cat_id = ObjectId(callback.data.split(":")[1])
    albums = await db.get_albums(cat_id)
    if not albums:
        await callback.answer(t("albums_empty", lang))
        return
    await callback.message.edit_text(
        t("albums_header", lang),
        parse_mode="HTML",
        reply_markup=albums_kb(albums, cat_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "albums_back")
async def albums_back(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    cats = await db.get_categories()
    await callback.message.edit_text(
        t("cats_header", lang),
        parse_mode="HTML",
        reply_markup=categories_kb(cats, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "artists_all")
async def show_artists(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    from keyboards.inline import artists_kb
    artists = await db.get_all_artists()
    if not artists:
        await callback.answer(t("artists_empty", lang))
        return
    await callback.message.edit_text(
        t("artists_header", lang, n=len(artists)),
        parse_mode="HTML",
        reply_markup=artists_kb(artists, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("artist:"))
async def show_artist(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    from keyboards.inline import artist_albums_kb
    artist_id = ObjectId(callback.data.split(":")[1])
    artist = await db.get_artist(artist_id)
    if not artist:
        await callback.answer(t("error_generic", lang))
        return
    albums = await db.get_artist_albums(artist_id)
    if not albums:
        await callback.answer(t("artist_albums_empty", lang))
        return
    await callback.message.edit_text(
        t("artist_header", lang, name=artist["name"], n=len(albums)),
        parse_mode="HTML",
        reply_markup=artist_albums_kb(albums, artist_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("album:"))
async def show_album(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    album_id = ObjectId(callback.data.split(":")[1])
    album = await db.get_album(album_id)
    if not album:
        await callback.answer(t("error_generic", lang))
        return
    is_admin = callback.from_user.id in ADMIN_IDS
    text = f"📀 <b>{album['name']}</b>\n"
    if album.get("artist"):
        text += f"🎤 {album['artist']}\n"
    text += t("album_dl_label", lang, n=album.get("downloads", 0)) + "\n\n"
    text += t("album_actions_hint", lang)

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
        reply_markup=album_actions_kb(album_id, is_admin, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("songs:"))
async def show_songs(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    album_id = ObjectId(callback.data.split(":")[1])
    songs = await db.get_songs(album_id)
    if not songs:
        await callback.answer(t("songs_empty", lang))
        return
    await callback.message.edit_text(
        t("songs_header", lang, n=len(songs)),
        parse_mode="HTML",
        reply_markup=songs_kb(songs, album_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "songs_all")
async def show_all_songs(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    cats = await db.get_categories()
    if not cats:
        await callback.answer(t("cats_empty", lang))
        return
    await callback.message.edit_text(
        t("cats_header", lang),
        parse_mode="HTML",
        reply_markup=categories_kb(cats, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "popular")
async def show_popular(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    from keyboards.inline import popular_songs_kb
    songs = await db.db.songs.find().sort("downloads", -1).limit(10).to_list(length=10)
    if not songs:
        await callback.answer(t("popular_empty", lang))
        return
    await callback.message.edit_text(
        t("popular_header", lang),
        parse_mode="HTML",
        reply_markup=popular_songs_kb(songs, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "songs_new")
async def show_new_songs(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    from keyboards.inline import search_results_kb
    songs = await db.get_latest_songs(10)
    if not songs:
        await callback.answer(t("new_empty", lang))
        return
    await callback.message.edit_text(
        t("new_header", lang),
        parse_mode="HTML",
        reply_markup=search_results_kb(songs, lang),
    )
    await callback.answer()
