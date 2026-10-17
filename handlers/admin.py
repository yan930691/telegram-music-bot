import re
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.state import StateFilter
from aiogram.filters import Command
import logging
import html
import asyncio

from database import db, AUTO_CATEGORY
from config import ADMIN_IDS, CHANNEL_ID, BOT_TOKEN, TG_API_ID, TG_API_HASH
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
    album_actions_kb,
    move_album_cat_kb,
)
from utils.formatters import get_admin_panel_text, split_caption
from utils.converter import normalize_myanmar
from utils.metadata import read_audio_metadata, pick_song_title, extract_track_no
from utils.i18n import t, get_lang
from utils.translate import build_search_terms

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
    imp_wait_forward = State()


async def is_admin(user_id) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("done"))
async def done_command(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    current = await state.get_state()
    if current == AdminStates.upload_music.state:
        data = await state.get_data()
        pending = await _load_pending_batch(message.from_user.id)
        if not pending and not (data.get("pending_songs") or []):
            await message.answer(t("a_nothing_pending", lang))
            return
        await _apply_finish_upload(message, state)
    elif current == AdminStates.adding_songs.state:
        await _apply_finish_batch(message, state)
    else:
        pending = await _load_pending_batch(message.from_user.id)
        if pending:
            await _apply_finish_upload(message, state)
        else:
            await message.answer(t("a_no_flow", lang))


@router.message(Command("backfilltranslate"))
async def backfill_translate_command(message: Message):
    if not await is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    status_msg = await message.answer(t("a_bf_start", lang))
    last = {"n": 0}

    async def _progress(n):
        last["n"] = n
        try:
            await status_msg.edit_text(t("a_bf_progress", lang, n=n))
        except Exception:
            pass

    try:
        done = await db.backfill_translations(progress=_progress)
    except Exception as e:
        logging.exception("backfill failed")
        await status_msg.edit_text(t("a_bf_failed", lang, err=html.escape(str(e))))
        return
    if done == 0:
        await status_msg.edit_text(t("a_bf_none", lang))
    else:
        await status_msg.edit_text(t("a_bf_done", lang, n=done))


_bg_tasks = set()


async def _resolve_channel_peer(app, chat, on_wait=None):
    """Resolve a channel to an id Pyrogram can use.

    ``get_dialogs``/``get_chat_history`` are users-only, so a bot can only
    resolve a channel from its @username or from a peer it has already seen in
    an update. A bare numeric id for a private channel needs an access_hash,
    which a bot only learns when it receives any update from that channel. If
    ``on_wait`` is given we wait for such an update (e.g. the admin posts
    something in the channel).
    """
    try:
        return (await app.get_chat(chat)).id
    except Exception as e:
        logging.warning("Pyrogram get_chat(%s) failed: %s", chat, e)
    # Private channel given by numeric id: wait for an update that caches it.
    if str(chat).lstrip("-").isdigit():
        if on_wait:
            try:
                await on_wait()
            except Exception:
                pass
        for _ in range(45):  # ~90 seconds
            await asyncio.sleep(2)
            try:
                return (await app.get_chat(chat)).id
            except Exception:
                continue
    return chat


async def _enumerate_channel_audio_ids(on_wait=None):
    """List channel message ids that are audio, using MTProto (Pyrogram).

    The Bot API cannot read old channel history, and ``get_chat_history`` is
    users-only (``BOT_METHOD_INVALID`` for bots). ``channels.getMessages`` is
    bot-callable when explicit ids are given, so we probe id ranges in batches
    and keep the audio ones.
    """
    from pyrogram import Client

    # Numeric channel ids must be ints for MTProto; @usernames stay strings.
    chat = int(CHANNEL_ID) if str(CHANNEL_ID).lstrip("-").isdigit() else CHANNEL_ID
    ids = []
    app = Client(
        "channel_import",
        api_id=int(TG_API_ID),
        api_hash=TG_API_HASH,
        bot_token=BOT_TOKEN,
    )
    async with app:
        resolved = await _resolve_channel_peer(app, chat, on_wait=on_wait)
        batch = 200
        start = 1
        empty_streak = 0
        # Safety cap: stop after ~1,000,000 ids or 5 consecutive empty batches
        # (~1000 missing ids) so deleted gaps near the tail don't truncate us.
        while start <= 1_000_000:
            chunk = list(range(start, start + batch))
            msgs = await app.get_messages(resolved, message_ids=chunk)
            if not isinstance(msgs, list):
                msgs = [msgs]
            found = False
            for m in msgs:
                if m is None or getattr(m, "empty", False):
                    continue
                found = True
                is_audio = bool(getattr(m, "audio", None))
                if not is_audio:
                    doc = getattr(m, "document", None)
                    if doc and "audio" in (getattr(doc, "mime_type", "") or ""):
                        is_audio = True
                if is_audio:
                    ids.append(m.id)
            empty_streak = 0 if found else empty_streak + 1
            start += batch
            if empty_streak >= 5:
                break
    return ids


async def _run_channel_import(bot, status_msg, lang, admin_chat_id):
    from handlers.channel import process_channel_audio

    async def _on_wait():
        try:
            await status_msg.edit_text(t("a_imp_need_post", lang), parse_mode="HTML")
        except Exception:
            pass

    try:
        ids = await _enumerate_channel_audio_ids(on_wait=_on_wait)
    except Exception as e:
        logging.exception("Channel enumeration failed")
        msg = str(e)
        if "Peer id invalid" in msg or "PEER_ID_INVALID" in msg:
            try:
                await status_msg.edit_text(t("a_imp_need_forward", lang), parse_mode="HTML")
            except Exception:
                pass
            # Prompt admin to forward a channel message
            try:
                await message.bot.send_message(
                    admin_chat_id, t("a_imp_need_forward", lang), parse_mode="HTML"
                )
            except Exception:
                pass
            try:
                await state.set_state(AdminStates.imp_wait_forward)
            except Exception:
                pass
            return

    total = len(ids)
    added = replaced = skipped = 0
    for i, mid in enumerate(ids, 1):
        try:
            # Forward to the admin's own chat so the Bot API hands us a usable
            # file_id, then immediately delete the temporary forwarded copy.
            fwd = await bot.forward_message(
                chat_id=admin_chat_id, from_chat_id=CHANNEL_ID, message_id=mid)
            st = await process_channel_audio(bot, fwd, notify=False)
            if st == "added":
                added += 1
            elif st == "replaced":
                replaced += 1
            elif st == "skipped":
                skipped += 1
            try:
                await bot.delete_message(chat_id=admin_chat_id, message_id=fwd.message_id)
            except Exception:
                pass
        except Exception:
            logging.exception("Channel import failed for message %s", mid)
        if i % 10 == 0 or i == total:
            try:
                await status_msg.edit_text(
                    t("a_imp_progress", lang, scanned=i, total=total,
                      added=added, skipped=skipped))
            except Exception:
                pass

    try:
        await status_msg.edit_text(
            t("a_imp_done", lang, scanned=total, added=added,
              replaced=replaced, skipped=skipped))
    except Exception:
        pass


@router.message(Command("importchannel"))
async def import_channel_command(message: Message):
    if not await is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    if not CHANNEL_ID:
        await message.answer(t("a_imp_no_channel", lang), parse_mode="HTML")
        return
    if not (TG_API_ID and TG_API_HASH):
        await message.answer(t("a_imp_no_creds", lang), parse_mode="HTML")
        return
    status_msg = await message.answer(t("a_imp_start", lang))
    task = asyncio.create_task(
        _run_channel_import(message.bot, status_msg, lang, message.chat.id))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


# ---------------- Admin menu ----------------
@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    await callback.message.edit_text(
        get_admin_panel_text(lang), parse_mode="HTML", reply_markup=admin_main_kb(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_cat")
async def admin_add_cat(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    await state.set_state(AdminStates.waiting_cat_name)
    await callback.message.answer(t("a_add_cat_prompt", lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_add_album")
async def admin_add_album(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    cats = await db.get_categories()
    if not cats:
        await callback.answer(t("a_add_cat_empty", lang))
        return
    await state.set_state(AdminStates.waiting_album_cat)
    await callback.message.answer(
        t("a_choose_album_cat", lang),
        parse_mode="HTML",
        reply_markup=album_add_cat_kb(cats, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_song")
async def admin_add_song(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    cats = await db.get_categories()
    if not cats:
        await callback.answer(t("a_add_song_first_cat", lang))
        return
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(text=f"🎵 {cat['name']}", callback_data=f"addsong_cat:{cat['_id']}")
    builder.button(text=t("back", lang), callback_data="admin_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        t("a_choose_song_cat", lang),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addsong_cat:"))
async def addsong_cat(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    cat_id = ObjectId(callback.data.split(":")[1])
    albums = await db.get_albums(cat_id)
    if not albums:
        await callback.answer(t("a_no_album_in_cat", lang))
        return
    builder = InlineKeyboardBuilder()
    for album in albums:
        builder.button(text=f"📀 {album['name']}", callback_data=f"addsong_album:{album['_id']}")
    builder.button(text=t("back", lang), callback_data="admin_add_song")
    builder.adjust(1)
    await callback.message.edit_text(
        t("a_choose_song_album", lang),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addsong_album:"))
async def addsong_album(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    album_id = ObjectId(callback.data.split(":")[1])
    await _begin_song_batch(callback.message, state, album_id, lang)
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    stats = await db.get_stats()
    text = (
        t("stats_header", lang) + "\n\n"
        + t("stats_songs", lang, n=stats["songs"]) + "\n"
        + t("stats_albums", lang, n=stats["albums"]) + "\n"
        + t("stats_users", lang, n=stats["users"])
    )
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=back_to_cats_kb(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_delete_menu")
async def admin_delete_menu(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    await callback.message.edit_text(
        t("a_delete_choose", lang),
        parse_mode="HTML",
        reply_markup=admin_delete_choice_kb(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "del_pick_cat")
async def delete_cat_pick(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    cats = await db.get_categories()
    if not cats:
        await callback.answer(t("a_del_no_cat", lang))
        return
    await callback.message.edit_text(
        t("a_del_choose_cat", lang),
        parse_mode="HTML",
        reply_markup=admin_delete_menu_kb(cats, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "del_pick_album")
async def delete_album_pick(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    albums = await db.get_all_albums()
    if not albums:
        await callback.answer(t("a_del_no_album", lang))
        return
    await callback.message.edit_text(
        t("a_del_choose_album", lang),
        parse_mode="HTML",
        reply_markup=admin_album_delete_kb(albums, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "del_pick_song")
async def delete_song_pick(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    songs = await db.get_all_songs()
    if not songs:
        await callback.answer(t("a_del_no_song", lang))
        return
    await callback.message.edit_text(
        t("a_del_choose_song", lang),
        parse_mode="HTML",
        reply_markup=admin_song_delete_kb(songs, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_album:"))
async def delete_album_confirm(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    album_id = ObjectId(callback.data.split(":")[1])
    album = await db.get_album(album_id)
    count = await db.db.songs.count_documents({"album_id": album_id})
    album_name = album["name"] if album else ""
    await callback.message.edit_text(
        t("a_del_album_confirm", lang, name=html.escape(album_name), n=count),
        parse_mode="HTML",
        reply_markup=admin_confirm_delete_kb(f"del_album:{album_id}", "del_pick_album", lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_album:"))
async def confirm_delete_album(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    album_id = ObjectId(callback.data.split(":")[1])
    album = await db.get_album(album_id)
    artist_id = album.get("artist_id") if album else None
    await db.delete_album(album_id)
    if artist_id:
        await db.delete_artist_if_empty(artist_id)
    await callback.answer(t("a_del_album_done", lang))
    albums = await db.get_all_albums()
    if albums:
        await callback.message.edit_text(
            t("a_del_choose_album", lang),
            parse_mode="HTML",
            reply_markup=admin_album_delete_kb(albums, lang),
        )
    else:
        await callback.message.edit_text(
            t("a_done_all", lang, what=t("a_what_albums", lang)),
            parse_mode="HTML",
            reply_markup=admin_main_kb(lang),
        )


@router.callback_query(F.data.startswith("move_album:"))
async def move_album_pick(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    album_id = ObjectId(callback.data.split(":")[1])
    cats = await db.get_categories()
    if not cats:
        await callback.answer(t("a_move_no_cat", lang))
        return
    await callback.message.edit_text(
        t("a_move_pick", lang),
        parse_mode="HTML",
        reply_markup=move_album_cat_kb(album_id, cats, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("movecat:"))
async def move_album_to_cat(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    _, album_s, cat_s = callback.data.split(":")
    album_id = ObjectId(album_s)
    cat_id = ObjectId(cat_s)
    await db.update_album(album_id, category_id=cat_id)
    album = await db.get_album(album_id)
    cat = await db.get_category(cat_id)
    album_name = album["name"] if album else ""
    cat_name = cat["name"] if cat else ""
    await callback.message.edit_text(
        t("a_move_done", lang, album=html.escape(album_name), cat=html.escape(cat_name)),
        parse_mode="HTML",
        reply_markup=album_actions_kb(album_id, True, lang),
    )
    await callback.answer(t("a_move_done", lang, album=album_name, cat=cat_name))


@router.callback_query(F.data.startswith("del_song:"))
async def delete_song_confirm(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    song_id = ObjectId(callback.data.split(":")[1])
    song = await db.get_song(song_id)
    song_title = song["title"] if song else ""
    await callback.message.edit_text(
        t("a_del_song_confirm", lang, name=html.escape(song_title)),
        parse_mode="HTML",
        reply_markup=admin_confirm_delete_kb(f"del_song:{song_id}", "del_pick_song", lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_song:"))
async def confirm_delete_song(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    song_id = ObjectId(callback.data.split(":")[1])
    await db.delete_song(song_id)
    await callback.answer(t("a_del_song_done", lang))
    songs = await db.get_all_songs()
    if songs:
        await callback.message.edit_text(
            t("a_del_choose_song", lang),
            parse_mode="HTML",
            reply_markup=admin_song_delete_kb(songs, lang),
        )
    else:
        await callback.message.edit_text(
            t("a_done_all", lang, what=t("a_what_songs", lang)),
            parse_mode="HTML",
            reply_markup=admin_main_kb(lang),
        )


@router.callback_query(F.data.startswith("del_cat:"))
async def delete_category_confirm(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    cat_id = ObjectId(callback.data.split(":")[1])
    cat = await db.get_category(cat_id)
    album_count = await db.db.albums.count_documents({"category_id": cat_id})
    cat_name = cat["name"] if cat else ""
    await callback.message.edit_text(
        t("a_del_cat_confirm", lang, name=html.escape(cat_name), n=album_count),
        parse_mode="HTML",
        reply_markup=admin_confirm_delete_kb(f"del_cat:{cat_id}", "del_pick_cat", lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_cat:"))
async def confirm_delete_category(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    cat_id = ObjectId(callback.data.split(":")[1])
    albums = await db.get_albums(cat_id)
    for album in albums:
        artist_id = album.get("artist_id")
        await db.delete_album(album["_id"])
        if artist_id:
            await db.delete_artist_if_empty(artist_id)
    await db.delete_category(cat_id)
    await callback.answer(t("a_del_cat_done", lang))
    cats = await db.get_categories()
    if cats:
        await callback.message.edit_text(
            t("a_del_choose_cat", lang),
            parse_mode="HTML",
            reply_markup=admin_delete_menu_kb(cats, lang),
        )
    else:
        await callback.message.edit_text(
            t("a_done_all", lang, what=t("a_what_cats", lang)),
            parse_mode="HTML",
            reply_markup=admin_main_kb(lang),
        )


# ---------------- New: Upload album with auto artist grouping ----------------

async def _ask_upload_category(callback: CallbackQuery, lang):
    cats = await db.get_categories()
    if not cats:
        await callback.answer(t("a_upload_first_cat", lang))
        return
    await callback.message.edit_text(
        t("a_upload_choose_cat", lang),
        parse_mode="HTML",
        reply_markup=upload_cat_kb(cats, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_upload")
async def admin_upload(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    await _ask_upload_category(callback, lang)


@router.message(Command("upload"))
async def upload_command(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not await is_admin(message.from_user.id):
        await message.answer(t("not_admin_short", lang))
        return
    cats = await db.get_categories()
    if not cats:
        await message.answer(t("a_upload_first_cat", lang))
        return
    await message.answer(
        t("a_upload_choose_cat", lang),
        parse_mode="HTML",
        reply_markup=upload_cat_kb(cats, lang),
    )


@router.callback_query(F.data.startswith("upcat:"))
async def upload_choose_cat(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    cat_id = ObjectId(callback.data.split(":")[1])
    await db.save_pending_upload(
        callback.from_user.id,
        cat_id=cat_id,
        cover="",
        album_name="",
        pending_songs=[],
    )
    await state.set_data(
        {"cat_id": cat_id, "cover": "", "album_name": "", "pending_songs": []}
    )
    await state.set_state(AdminStates.upload_music)
    await callback.message.answer(
        t("a_upload_started", lang),
        parse_mode="HTML",
        reply_markup=upload_batch_kb(lang),
    )
    await callback.answer()


async def _parse_song_meta(message: Message, current_album: str):
    """Return (title, artist, album_from_caption, file_id, file_size, duration)."""
    caption_parts = split_caption(message.caption)
    if message.audio:
        title = pick_song_title(message.audio.file_name or "", message.audio.title or "")
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

    if len(caption_parts) >= 3:
        default_album = caption_parts[0]
        title = caption_parts[1] or title
        artist = caption_parts[2] or artist
    elif len(caption_parts) == 2:
        title = caption_parts[0] or title
        artist = caption_parts[1] or artist
    elif len(caption_parts) == 1:
        title = caption_parts[0] or title

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
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    cover = message.photo[-1].file_id
    album = (message.caption or "").strip()
    await db.save_pending_upload(message.from_user.id, cover=cover)
    await state.update_data(cover=cover)
    text = t("a_upload_cover_received", lang)
    if album:
        await db.save_pending_upload(message.from_user.id, album_name=album)
        await state.update_data(album_name=album)
        text += "\n" + t("a_upload_album_name_set", lang, name=html.escape(album))
    text += "\n\n" + t("a_upload_send_songs", lang)
    await message.answer(text, parse_mode="HTML", reply_markup=upload_batch_kb(lang))


async def _append_to_pending(message: Message, state: FSMContext) -> list:
    """Append the forwarded audio to the persisted upload batch. Returns updated pending list."""
    data = await state.get_data()
    pending = await _load_pending_batch(message.from_user.id)
    title, artist, album, file_id, file_size, duration = await _parse_song_meta(
        message, data.get("album_name", "") or ""
    )
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
    await db.append_pending_song(message.from_user.id, pending[-1])
    await state.update_data(pending_songs=pending, album_name=album or data.get("album_name", ""))
    return pending


@router.message(AdminStates.upload_music, F.audio | F.document)
async def upload_song(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if message.document and "audio" not in (message.document.mime_type or ""):
        await message.answer(t("a_upload_audio_only", lang), parse_mode="HTML")
        return
    try:
        pending = await _append_to_pending(message, state)
    except Exception:
        await message.answer(
            t("a_upload_unreadable", lang),
            parse_mode="HTML",
            reply_markup=upload_batch_kb(lang),
        )
        return
    title = pending[-1]["title"]
    artist = pending[-1]["artist"]
    album = pending[-1]["album"]
    artist_line = f"\n🎤 {html.escape(artist)}" if artist else t("a_upload_no_artist", lang)
    line = t("a_upload_song_line", lang, n=len(pending), title=html.escape(title),
             artist_line=artist_line, album=html.escape(album) or "—")
    await message.answer(line, parse_mode="HTML", reply_markup=upload_batch_kb(lang))


@router.message(AdminStates.upload_music, F.text)
async def upload_set_album_name(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        return
    lang = await get_lang(message.from_user.id)
    album = normalize_myanmar(message.text.strip())
    await db.save_pending_upload(message.from_user.id, album_name=album)
    await state.update_data(album_name=album)
    await message.answer(
        t("a_upload_set_album", lang, name=html.escape(album)),
        parse_mode="HTML",
        reply_markup=upload_batch_kb(lang),
    )


@router.message(AdminStates.upload_music)
async def upload_wrong_type(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("a_upload_wrong_type", lang), parse_mode="HTML")


async def _announce_upload(bot, summary: str):
    if not CHANNEL_ID:
        return
    try:
        await bot.send_message(CHANNEL_ID, summary, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Upload announce failed: {e}")


async def _load_pending_batch(user_id) -> list:
    """Return the persisted pending upload batch (survives bot restarts)."""
    batch = await db.get_pending_upload(user_id)
    if batch and batch.get("pending_songs"):
        return list(batch["pending_songs"])
    return []


async def _apply_finish_upload(reply_target, state: FSMContext) -> bool:
    """Finish the /upload batch flow. reply_target must have .answer() and .bot."""
    user_id = reply_target.chat.id
    lang = await get_lang(user_id)
    data = await state.get_data()
    batch = await db.get_pending_upload(user_id) or {}
    pending = batch.get("pending_songs") or data.get("pending_songs") or []
    raw_cat_id = data.get("cat_id") or batch.get("cat_id")
    cover = (data.get("cover") or batch.get("cover") or "").strip()
    batch_album_name = data.get("album_name", "") or batch.get("album_name", "") or ""

    # Never leave an album without a category (that makes it invisible in the
    # category browser) — fall back to the auto-save category.
    auto_cat = await db.get_or_create_category(AUTO_CATEGORY)
    auto_cat_id = auto_cat["_id"] if auto_cat else None
    cat_id = raw_cat_id or auto_cat_id
    # Only an explicitly chosen real category should move an existing album;
    # the auto bucket never steals albums from their category.
    move_category = raw_cat_id is not None and raw_cat_id != auto_cat_id

    artists_used = {}
    albums_used = {}
    artists_order = []
    albums_order = []
    songs_by_album = {}
    count = 0
    skipped = 0

    for s in pending:
        artist_name = (s.get("artist") or "").strip() or "အမည်မသိ"
        album_name = (s.get("album") or "").strip() or batch_album_name
        if not album_name:
            album_name = (artist_name + " album").strip()

        artist = await db.get_or_create_artist(artist_name)
        album = await db.get_or_create_album(
            album_name,
            artist=artist_name,
            category_id=cat_id,
            cover=cover,
            artist_id=artist["_id"],
            move_category=move_category,
        )
        if album_name not in artists_used:
            artists_used[album_name] = artist_name
            artists_order.append(artist_name)
        if album_name not in albums_used:
            albums_used[album_name] = album["_id"]
            albums_order.append(album_name)

        track_no = extract_track_no(s["title"])
        terms = await build_search_terms(s["title"], artist_name, album_name)
        status, _song = await db.save_song_dedup(
            s["title"],
            album["_id"],
            s["file_id"],
            s["file_size"],
            s["duration"],
            artist_id=artist["_id"],
            track_no=track_no,
            search_terms=terms,
        )
        if status == "skipped":
            skipped += 1
            continue
        count += 1
        songs_by_album.setdefault(album_name, []).append((track_no, s["title"]))

    await state.clear()
    await db.clear_pending_upload(user_id)

    lines = [t("a_upload_finished", lang, songs=count,
               artists=len(set(artists_order)), albums=len(albums_order),
               listing="__LISTING__")]
    text = lines[0]
    listing = ""
    for i, a in enumerate(albums_order, 1):
        listing += f"{i}. {html.escape(a)} — {html.escape(artists_used[a])}\n"
    if songs_by_album:
        listing += "\n"
        for a in albums_order:
            songs = sorted(
                songs_by_album.get(a, []), key=lambda x: (x[0] is None, x[0] or 0)
            )
            if not songs:
                continue
            listing += f"📀 <b>{html.escape(a)}</b>\n"
            for i, (track_no, title) in enumerate(songs, 1):
                listing += f"№{track_no or i}. {html.escape(title)}\n"
            listing += "\n"
    if skipped:
        listing += f"ℹ️ Skipped duplicates: {skipped}\n"
    text = text.replace("__LISTING__", listing)

    await reply_target.answer(text, parse_mode="HTML")

    artists_list = "၊ ".join(sorted(set(artists_order)))
    sum_text = t("announce_new", lang, n=count,
                 artists=artists_list or "အမည်မသိ")
    await _announce_upload(reply_target.bot, sum_text)
    return True


@router.callback_query(F.data == "finish_upload")
async def finish_upload(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    pending = await _load_pending_batch(callback.from_user.id)
    if not pending:
        await callback.answer(t("a_nothing_pending", lang), show_alert=True)
        return
    await _apply_finish_upload(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "cancel_upload")
async def cancel_upload(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    await state.clear()
    await db.clear_pending_upload(callback.from_user.id)
    await callback.message.answer(
        t("a_upload_cancelled", lang),
        parse_mode="HTML",
        reply_markup=admin_main_kb(lang),
    )
    await callback.answer()


# ---------------- Generic admin forward auto-save (no active FSM) ----------------

async def _resume_pending_upload(message: Message, state: FSMContext, pending: list):
    """The bot restarted mid-/upload, so FSM was wiped but the batch survives in DB.
    Re-enter the upload flow so this forward keeps queuing into the same album."""
    lang = await get_lang(message.from_user.id)
    batch = await db.get_pending_upload(message.from_user.id) or {}
    await state.set_data(
        {
            "cat_id": batch.get("cat_id"),
            "cover": batch.get("cover", "") or "",
            "album_name": batch.get("album_name", "") or "",
            "pending_songs": pending,
        }
    )
    await state.set_state(AdminStates.upload_music)
    await _append_to_pending(message, state)
    new_pending = await _load_pending_batch(message.from_user.id)
    s = new_pending[-1]
    artist_line = f"\n🎤 {html.escape(s['artist'])}" if s.get("artist") else t("a_upload_no_artist", lang)
    line = t("a_upload_song_line", lang, n=len(new_pending), title=html.escape(s["title"]),
             artist_line=artist_line, album=html.escape(s.get("album") or "") or "—")
    await message.answer(line, parse_mode="HTML", reply_markup=upload_batch_kb(lang))


@router.message(StateFilter(None), F.audio | F.document)
async def auto_save_forwarded(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not await is_admin(message.from_user.id):
        return
    if message.chat.type != "private":
        return
    if message.document and "audio" not in (message.document.mime_type or ""):
        return
    pending = await _load_pending_batch(message.from_user.id)
    if not pending:
        auto_cat = await db.get_or_create_category(AUTO_CATEGORY)
        await db.save_pending_upload(
            message.from_user.id,
            album_name="",
            cat_id=auto_cat["_id"] if auto_cat else None,
        )
        pending = await _load_pending_batch(message.from_user.id)
    try:
        await _resume_pending_upload(message, state, pending)
    except Exception as e:
        logging.warning(f"Auto-save failed: {e}")
        await message.answer(
            t("a_upload_save_failed", lang, err=html.escape(str(e))),
            parse_mode="HTML",
        )


# ---------------- FSM states ----------------

@router.message(AdminStates.waiting_cat_name)
async def receive_cat_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    name = message.text.strip()
    await state.update_data(cat_name=name)
    await state.set_state(AdminStates.waiting_cat_desc)
    await message.answer(t("a_cat_desc_prompt", lang), parse_mode="HTML")


@router.message(AdminStates.waiting_cat_desc, F.text == "/skip")
async def skip_cat_desc(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    await db.add_category(data["cat_name"], "")
    await state.clear()
    await message.answer(t("a_cat_added", lang), parse_mode="HTML", reply_markup=admin_main_kb(lang))


@router.message(AdminStates.waiting_cat_desc)
async def receive_cat_desc(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    desc = message.text.strip()
    data = await state.get_data()
    await db.add_category(data["cat_name"], desc)
    await state.clear()
    await message.answer(t("a_cat_added", lang), parse_mode="HTML", reply_markup=admin_main_kb(lang))


@router.callback_query(F.data.startswith("add_album:"))
async def add_album_to_cat(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    cat_id = ObjectId(callback.data.split(":")[1])
    await state.update_data(album_cat_id=cat_id)
    await state.set_state(AdminStates.waiting_album_name)
    await callback.message.answer(t("a_album_name_prompt", lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(AdminStates.waiting_album_cat, F.data.startswith("albadd_cat:"))
async def choose_album_cat(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    cat_id = ObjectId(callback.data.split(":")[1])
    await state.update_data(album_cat_id=cat_id)
    await state.set_state(AdminStates.waiting_album_name)
    await callback.message.answer(t("a_album_name_prompt", lang), parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_album_name)
async def receive_album_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    name = message.text.strip()
    await state.update_data(album_name=name)
    await state.set_state(AdminStates.waiting_album_artist)
    await message.answer(t("a_album_artist_prompt", lang), parse_mode="HTML")


@router.message(AdminStates.waiting_album_artist, F.text == "/skip")
async def skip_album_artist(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.update_data(album_artist="")
    await state.set_state(AdminStates.waiting_album_cover)
    await message.answer(t("a_album_cover_prompt", lang), parse_mode="HTML")


@router.message(AdminStates.waiting_album_artist)
async def receive_album_artist(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.update_data(album_artist=message.text.strip())
    await state.set_state(AdminStates.waiting_album_cover)
    await message.answer(t("a_album_cover_prompt", lang), parse_mode="HTML")


@router.message(AdminStates.waiting_album_cover, F.photo)
async def receive_album_cover(message: Message, state: FSMContext):
    cover = message.photo[-1].file_id
    await _finish_add_album(message, state, cover)


@router.message(AdminStates.waiting_album_cover, F.text == "/skip")
async def skip_album_cover(message: Message, state: FSMContext):
    await _finish_add_album(message, state, "")


@router.message(AdminStates.waiting_album_cover)
async def album_cover_wrong_type(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("a_album_cover_wrong", lang), parse_mode="HTML")


async def _finish_add_album(message: Message, state: FSMContext, cover=""):
    lang = await get_lang(message.from_user.id)
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
    artist_line = t("a_album_added_artist", lang, artist=html.escape(artist)) if artist else ""
    await message.answer(
        t("a_album_added", lang, name=html.escape(name), artist_line=artist_line),
        parse_mode="HTML",
        reply_markup=album_added_kb(album_id, lang),
    )


# ---------------- Song upload (batch) ----------------

async def _begin_song_batch(message: Message, state: FSMContext, album_id, lang):
    album = await db.get_album(album_id)
    album_name = album["name"] if album else ""
    await state.set_data({"song_album_id": album_id, "song_count": 0, "pending_title": None})
    await state.set_state(AdminStates.adding_songs)
    await message.answer(
        t("a_batch_begin", lang, album=html.escape(album_name)),
        parse_mode="HTML",
        reply_markup=adding_songs_kb(album_id, lang),
    )


@router.callback_query(F.data.startswith("add_song:"))
async def start_song_upload(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    album_id = ObjectId(callback.data.split(":")[1])
    await _begin_song_batch(callback.message, state, album_id, lang)
    await callback.answer()


@router.message(AdminStates.adding_songs, F.audio | F.document)
async def add_batch_song(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    album_id = data["song_album_id"]
    album_doc = await db.get_album(album_id)
    album_name = album_doc["name"] if album_doc else ""
    custom_title = data.get("pending_title") or ""

    if message.audio:
        file_id = message.audio.file_id
        file_size = message.audio.file_size or 0
        duration = message.audio.duration or 0
        auto_title = pick_song_title(message.audio.file_name or "", message.audio.title or "")
    else:
        if "audio" not in (message.document.mime_type or ""):
            await message.answer(t("a_upload_audio_only", lang), parse_mode="HTML")
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

    track_no = extract_track_no(title)
    artist_name = (album_doc or {}).get("artist", "") or ""
    terms = await build_search_terms(title, artist_name, album_name)
    status, _song = await db.save_song_dedup(
        title, album_id, file_id, file_size, duration, track_no=track_no,
        search_terms=terms,
    )
    count = data.get("song_count", 0) + 1
    await state.update_data(song_count=count, pending_title=None)

    if status == "skipped":
        msg = t("ch_duplicate", lang)
    else:
        msg = t("a_batch_song_added", lang, n=count, title=html.escape(title),
                album=html.escape(album_name))
    await message.answer(msg, parse_mode="HTML", reply_markup=adding_songs_kb(album_id, lang))


@router.message(AdminStates.adding_songs, F.text)
async def set_batch_song_title(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        return
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    await state.update_data(pending_title=message.text.strip())
    await message.answer(
        t("a_batch_title_set", lang, title=html.escape(message.text.strip())),
        parse_mode="HTML",
        reply_markup=adding_songs_kb(data["song_album_id"], lang),
    )


@router.message(AdminStates.adding_songs)
async def batch_add_wrong_type(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("a_batch_audio_only", lang), parse_mode="HTML")


async def _apply_finish_batch(reply_target, state: FSMContext, album_id=None) -> bool:
    """Finish the add-songs-to-existing-album flow. reply_target must have .answer()."""
    user_id = reply_target.chat.id
    lang = await get_lang(user_id)
    data = await state.get_data()
    if album_id is None:
        album_id = data.get("song_album_id")
    count = data.get("song_count", 0)
    album = await db.get_album(album_id)
    album_name = album["name"] if album else ""
    await state.clear()

    if count == 0:
        text = t("a_batch_none", lang)
        kb = album_added_kb(album_id, lang)
        ok = False
    else:
        text = t("a_batch_done", lang, album=html.escape(album_name), n=count)
        kb = song_added_kb(album_id, lang)
        ok = True
    await reply_target.answer(text, parse_mode="HTML", reply_markup=kb)
    return ok


@router.callback_query(F.data.startswith("finish_songs:"))
async def finish_batch(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    album_id = ObjectId(callback.data.split(":")[1])
    await _apply_finish_batch(callback.message, state, album_id=album_id)
    await callback.answer()


@router.callback_query(F.data == "cancel_batch")
async def cancel_batch(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    if not await is_admin(callback.from_user.id):
        await callback.answer(t("not_admin", lang))
        return
    await state.clear()
    await callback.message.answer(
        t("a_batch_cancelled", lang),
        parse_mode="HTML",
        reply_markup=admin_main_kb(lang),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.imp_wait_forward), F.forward_from_chat)
async def imp_got_forward(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    fch = message.forward_from_chat
    if fch and str(fch.id) == str(CHANNEL_ID):
        try:
            await state.clear()
        except Exception:
            pass
        await message.answer(t("a_imp_forward_ok", lang), parse_mode="HTML")
        return
    await message.answer(t("a_imp_need_forward", lang), parse_mode="HTML")


@router.message(StateFilter(AdminStates.imp_wait_forward))
async def imp_wait_hint(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("a_imp_need_forward", lang), parse_mode="HTML")
