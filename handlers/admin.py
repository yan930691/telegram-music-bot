from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.state import StateFilter
from aiogram.filters import Command
import logging
import html

from database import db
from config import ADMIN_IDS, CHANNEL_ID
from bson import ObjectId
from keyboards.inline import (
    admin_main_kb,
    admin_delete_menu_kb,
    admin_delete_choice_kb,
    admin_album_delete_kb,
    admin_song_delete_kb,
    admin_confirm_delete_kb,
    album_add_cat_kb,
    album_added_kb,
    song_added_kb,
    adding_songs_kb,
    categories_kb,
    albums_kb,
    back_to_cats_kb,
    upload_cat_kb,
    upload_batch_kb,
)
from utils.formatters import split_caption
from utils.converter import normalize_myanmar
from utils.metadata import read_audio_metadata

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
    upload_cat = State()
    upload_music = State()


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
    await callback.message.edit_text(
        "🗑 <b>ဖျက်လိုသည့် အမျိုးအစား ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=admin_delete_choice_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "del_pick_cat")
async def delete_cat_pick(callback: CallbackQuery):
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


@router.callback_query(F.data == "del_pick_album")
async def delete_album_pick(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    albums = await db.get_all_albums()
    if not albums:
        await callback.answer("⚠️ ဖျက်ရန် Album မရှိပါ!")
        return
    await callback.message.edit_text(
        "🗑 <b>ဖျက်မည့် Album ရွေးပါ:</b>\n\n"
        f"(Album ဖျက်လျှင် ထဲမှ သီချင်းများလည်း ပါ ဖျက်ပါမည်)",
        parse_mode="HTML",
        reply_markup=admin_album_delete_kb(albums),
    )
    await callback.answer()


@router.callback_query(F.data == "del_pick_song")
async def delete_song_pick(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    songs = await db.get_all_songs()
    if not songs:
        await callback.answer("⚠️ ဖျက်ရန် သီချင်း မရှိပါ!")
        return
    await callback.message.edit_text(
        "🗑 <b>ဖျက်မည့် သီချင်း ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=admin_song_delete_kb(songs),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_album:"))
async def delete_album_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    album_id = ObjectId(callback.data.split(":")[1])
    album = await db.get_album(album_id)
    count = await db.db.songs.count_documents({"album_id": album_id})
    album_name = album["name"] if album else ""
    await callback.message.edit_text(
        f"⚠️ <b>{html.escape(album_name)}</b> ကို ဖျက်မည်လား?\n\n"
        f"ထဲမှ သီချင်း <b>{count}</b> ပုဒ်လည်း ပါ ဖျက်ပါမည်။",
        parse_mode="HTML",
        reply_markup=admin_confirm_delete_kb(f"del_album:{album_id}", "del_pick_album"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_album:"))
async def confirm_delete_album(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    album_id = ObjectId(callback.data.split(":")[1])
    album = await db.get_album(album_id)
    artist_id = album.get("artist_id") if album else None
    await db.delete_album(album_id)
    if artist_id:
        await db.delete_artist_if_empty(artist_id)
    await callback.answer("🗑 Album ဖျက်ပြီးပါပြီ!")
    albums = await db.get_all_albums()
    if albums:
        await callback.message.edit_text(
            "🗑 <b>ဖျက်မည့် Album ရွေးပါ:</b>",
            parse_mode="HTML",
            reply_markup=admin_album_delete_kb(albums),
        )
    else:
        await callback.message.edit_text(
            "✅ <b>ဖျက်ပြီးပါပြီ!</b>\n\nAlbum မကျန်တော့ပါ။",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )


@router.callback_query(F.data.startswith("del_song:"))
async def delete_song_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    song_id = ObjectId(callback.data.split(":")[1])
    song = await db.get_song(song_id)
    song_title = song["title"] if song else ""
    await callback.message.edit_text(
        f"⚠️ <b>{html.escape(song_title)}</b> ကို ဖျက်မည်လား?",
        parse_mode="HTML",
        reply_markup=admin_confirm_delete_kb(f"del_song:{song_id}", "del_pick_song"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_song:"))
async def confirm_delete_song(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    song_id = ObjectId(callback.data.split(":")[1])
    await db.delete_song(song_id)
    await callback.answer("🗑 သီချင်း ဖျက်ပြီးပါပြီ!")
    songs = await db.get_all_songs()
    if songs:
        await callback.message.edit_text(
            "🗑 <b>ဖျက်မည့် သီချင်း ရွေးပါ:</b>",
            parse_mode="HTML",
            reply_markup=admin_song_delete_kb(songs),
        )
    else:
        await callback.message.edit_text(
            "✅ <b>ဖျက်ပြီးပါပြီ!</b>\n\nသီချင်း မကျန်တော့ပါ။",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )


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


# ---------------- New: Upload album with auto artist grouping ----------------

async def _ask_upload_category(callback: CallbackQuery):
    cats = await db.get_categories()
    if not cats:
        await callback.answer("⚠️ ဦးစွာ အမျိုးအစား (category) ထည့်ပါ!")
        return
    await callback.message.edit_text(
        "📀 <b>Album တင်မည့် အမျိုးအစား ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=upload_cat_kb(cats),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_upload")
async def admin_upload(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    await _ask_upload_category(callback)


@router.message(Command("upload"))
async def upload_command(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ သင်သည် အက်ဒမင် မဟုတ်ပါ။")
        return
    cats = await db.get_categories()
    if not cats:
        await message.answer("⚠️ ဦးစွာ အမျိုးအစား (category) ထည့်ပါ!")
        return
    await message.answer(
        "📀 <b>Album တင်မည့် အမျိုးအစား ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=upload_cat_kb(cats),
    )


@router.callback_query(F.data.startswith("upcat:"))
async def upload_choose_cat(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    cat_id = ObjectId(callback.data.split(":")[1])
    await state.set_data(
        {"cat_id": cat_id, "cover": "", "album_name": "", "pending_songs": []}
    )
    await state.set_state(AdminStates.upload_music)
    await callback.message.answer(
        "🎼 <b>Album တင်ခြင်း စတင်နေသည်</b>\n\n"
        "1️⃣ ကာဗာပုံ (optional): photo ပို့ပါ — caption ထဲ Album နာမည် ရေးနိုင်သည်\n"
        "   (ပုံမလိုရင် ဤအဆင့် ကျော်နိုင်သည်)\n"
        "2️⃣ သီချင်းများ: audio file / forward ပို့ပါ — အားလုံး ပို့ပြီးရင် "
        "\"✅ ပြီးပါပြီ\" နှိပ်ပါ\n\n"
        "💡 <b>Artist grouping:</b> သီချင်း audio ရဲ့ performer (or caption "
        "'Song | Artist') နဲ့ အနုပညာရှင်ကို ခွဲသိမ်းပါမည် — name တူရင် "
        "အနုပညာရှင် တစ်ဦးအောက် ပြန်စုပါမည်",
        parse_mode="HTML",
        reply_markup=upload_batch_kb(),
    )
    await callback.answer()


async def _parse_song_meta(message: Message, current_album: str):
    """Return (title, artist, album_from_caption) for an audio/document message."""
    caption_parts = split_caption(message.caption)
    if message.audio:
        title = message.audio.title or ""
        artist = message.audio.performer or ""
        file_id = message.audio.file_id
        file_size = message.audio.file_size or 0
        duration = message.audio.duration or 0
        default_album = current_album
    else:
        title = message.document.file_name or ""
        artist = ""
        file_id = message.document.file_id
        file_size = message.document.file_size or 0
        duration = 0
        default_album = current_album

    # Caption formats: "Song | Artist"  or  "Album | Song | Artist"
    if len(caption_parts) >= 3:
        default_album = caption_parts[0]
        title = caption_parts[1] or title
        artist = caption_parts[2] or artist
    elif len(caption_parts) == 2:
        title = caption_parts[0] or title
        artist = caption_parts[1] or artist
    elif len(caption_parts) == 1:
        title = caption_parts[0] or title

    # Fill gaps from the file's embedded metadata (album is never sent by
    # Telegram, so MP3 ID3 tags are the only reliable source for it).
    if not title or not artist or not default_album:
        meta = await read_audio_metadata(message.bot, file_id, file_size)
        if not title and meta.get("title"):
            title = meta["title"]
        if not artist and meta.get("artist"):
            artist = meta["artist"]
        if not default_album and meta.get("album"):
            default_album = meta["album"]

    if not title:
        title = "အမည်မသိ"
    if title.lower().endswith((".mp3", ".m4a", ".ogg", ".wav", ".opus")):
        title = title.rsplit(".", 1)[0]
    title = normalize_myanmar(title)
    artist = normalize_myanmar(artist)
    default_album = normalize_myanmar(default_album)
    return title, artist.strip(), default_album, file_id, file_size, duration


@router.message(AdminStates.upload_music, F.photo)
async def upload_cover(message: Message, state: FSMContext):
    data = await state.get_data()
    cover = message.photo[-1].file_id
    album = (message.caption or "").strip()
    await state.update_data(cover=cover)
    text = "🖼 <b>ကာဗာပုံ ရရှိပြီ!</b>"
    if album:
        await state.update_data(album_name=album)
        text += f"\n📀 Album နာမည်: <b>{html.escape(album)}</b>"
    text += "\n\nအခု သီချင်းများ ပို့ပါ 👇"
    await message.answer(text, parse_mode="HTML", reply_markup=upload_batch_kb())


@router.message(AdminStates.upload_music, F.audio | F.document)
async def upload_song(message: Message, state: FSMContext):
    if message.document and "audio" not in (message.document.mime_type or ""):
        await message.answer("⚠️ <b>အသံဖိုင် သာ ပို့နိုင်ပါသည်။</b>", parse_mode="HTML")
        return
    data = await state.get_data()
    title, artist, album, file_id, file_size, duration = await _parse_song_meta(
        message, data.get("album_name", "") or ""
    )
    pending = data.get("pending_songs") or []
    pending.append(
        {
            "title": title,
            "artist": artist,
            "album": album or "",
            "file_id": file_id,
            "file_size": file_size,
            "duration": duration,
        }
    )
    await state.update_data(pending_songs=pending, album_name=album or data.get("album_name", ""))
    line = f"📥 <b>သီချင်း ({len(pending)})</b> ✅\n\n🎵 <b>{html.escape(title)}</b>"
    if artist:
        line += f"\n🎤 {html.escape(artist)}"
    if not artist:
        line += "\n⚠️ အဆိုတော် နာမည် မပါပါ — caption 'Song | Artist' ဖြင့် ပို့နိုင်သည်"
    line += (
        f"\n📀 {html.escape(album) or '—'}\n\n"
        "ထပ်ပို့ပါ — ပြီးရင် \"✅ ပြီးပါပြီ\" နှိပ်ပါ 👇"
    )
    await message.answer(line, parse_mode="HTML", reply_markup=upload_batch_kb())


@router.message(AdminStates.upload_music, F.text)
async def upload_set_album_name(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        return
    album = normalize_myanmar(message.text.strip())
    await state.update_data(album_name=album)
    await message.answer(
        f"📀 <b>{html.escape(album)}</b>\n\n"
        "အခု သီချင်းများ ပို့ပါ 👇",
        parse_mode="HTML",
        reply_markup=upload_batch_kb(),
    )


@router.message(AdminStates.upload_music)
async def upload_wrong_type(message: Message):
    await message.answer(
        "⚠️ အသံဖိုင်ကို forward/ပို့ပါ၊ သို့မဟုတ် photo ပို့ပါ — ပြီးရင် \"✅ ပြီးပါပြီ\" နှိပ်ပါ။",
        parse_mode="HTML",
    )


async def _announce_upload(bot, summary: str):
    if not CHANNEL_ID:
        return
    try:
        await bot.send_message(CHANNEL_ID, summary, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Upload announce failed: {e}")


@router.callback_query(F.data == "finish_upload")
async def finish_upload(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ အက်ဒမင် မဟုတ်ပါ!")
        return
    data = await state.get_data()
    pending = data.get("pending_songs") or []
    cat_id = data.get("cat_id")
    cover = data.get("cover", "") or ""
    batch_album_name = data.get("album_name", "") or ""

    if not pending:
        await callback.answer("⚠️ သီချင်း မပို့ရသေးပါ!", show_alert=True)
        return

    artists_used = {}
    albums_used = {}
    artists_order = []
    albums_order = []
    count = 0

    for s in pending:
        artist_name = (s.get("artist") or "").strip() or "အမည်မသိ"
        album_name = (s.get("album") or "").strip() or batch_album_name
        if not album_name:
            album_name = (artist_name + " အယ်လ်ဘမ်").strip()

        artist = await db.get_or_create_artist(artist_name)
        album = await db.get_or_create_album(
            album_name,
            artist=artist_name,
            category_id=cat_id,
            cover=cover,
            artist_id=artist["_id"],
        )
        if album_name not in artists_used:
            artists_used[album_name] = artist_name
            artists_order.append(artist_name)
        if album_name not in albums_used:
            albums_used[album_name] = album["_id"]
            albums_order.append(album_name)

        await db.add_song(
            s["title"],
            album["_id"],
            s["file_id"],
            s["file_size"],
            s["duration"],
            artist_id=artist["_id"],
        )
        count += 1

    await state.clear()

    text = f"✅ <b>ထည့်ပြီးပါပြီ!</b>\n\n"
    text += f"🎵 သီချင်း: <b>{count}</b> ပုဒ်\n"
    text += f"🎤 အနုပညာရှင်: <b>{len(set(artists_order))}</b>\n"
    text += f"📀 Album: <b>{len(albums_order)}</b>\n\n"
    text += "<b>သိမ်းထားသော Album များ:</b>\n"
    for i, a in enumerate(albums_order, 1):
        text += f"{i}. {html.escape(a)} — {html.escape(artists_used[a])}\n"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

    artists_list = "၊ ".join(sorted(set(artists_order)))
    sum_text = (
        f"🆕 <b>သီချင်းအသစ် ရောက်ရှိသည်</b>\n\n"
        f"🎵 {count} ပုဒ် — 🎤 {artists_list or 'အမည်မသိ'}\n"
        f"🎧 Bot ၌ နားထောင်နိုင်ပါပြီ"
    )
    await _announce_upload(callback.bot, sum_text)


@router.callback_query(F.data == "cancel_upload")
async def cancel_upload(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "❌ <b>တင်ခြင်း ရပ်လိုက်ပါပြီ</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )
    await callback.answer()


# ---------------- Generic admin forward auto-save (no active FSM) ----------------

@router.message(StateFilter(None), F.audio | F.document)
async def auto_save_forwarded(message: Message):
    if not await is_admin(message.from_user.id):
        return
    if message.chat.type != "private":
        return
    if message.document and "audio" not in (message.document.mime_type or ""):
        return
    try:
        title, artist, album, file_id, file_size, duration = await _parse_song_meta(
            message, ""
        )
        existing = await db.db.songs.find_one({"file_id": file_id})
        if existing:
            await message.answer("ℹ️ ဤသီချင်းကို သိမ်းပြီးသား ဖြစ်ပါသည်။")
            return

        artist_doc = await db.get_or_create_artist(artist or "အမည်မသိ")
        album_name = album or f"{artist_doc['name']} — အယ်လ်ဘမ်"
        # Find an existing album for this artist, else create one via default category
        album_doc = await db.get_or_create_album(
            album_name,
            artist=artist_doc["name"],
            category_id=None,
            artist_id=artist_doc["_id"],
        )
        await db.add_song(
            title,
            album_doc["_id"],
            file_id,
            file_size,
            duration,
            artist_id=artist_doc["_id"],
        )
        await message.answer(
            f"✅ <b>သိမ်းပြီးပါပြီ!</b>\n\n"
            f"🎵 <b>{html.escape(title)}</b>\n"
            f"🎤 {html.escape(artist_doc['name'])}\n"
            f"📀 {html.escape(album_doc['name'])}",
            parse_mode="HTML",
        )
    except Exception as e:
        logging.warning(f"Auto-save failed: {e}")


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

    title = custom_title or auto_title
    if not title:
        meta = await read_audio_metadata(message.bot, file_id, file_size)
        title = meta.get("title") or ""
    title = title or "အမည်မသိ"
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
