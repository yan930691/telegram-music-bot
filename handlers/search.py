from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedAudio,
    InputTextMessageContent,
)
from aiogram.filters import Command
from database import db
from config import ADMIN_IDS
from keyboards.inline import (
    search_results_kb,
    main_menu_kb,
    artists_kb,
    admin_main_kb,
)
from utils.converter import normalize_myanmar
from utils.formatters import get_admin_panel_text
from utils.i18n import t, get_lang

router = Router()

PER_PAGE = 8

# Simple flag-based search: user taps 🔍 then types
SEARCHING_USERS = set()

# Store the last query per user so pagination buttons don't need to carry the
# (possibly Myanmar UTF-8) query in callback_data (64-byte Telegram limit).
LAST_SEARCH = {}


def _in_search_mode(message: Message) -> bool:
    return bool(message.from_user) and message.from_user.id in SEARCHING_USERS


@router.message(Command("search"))
async def search_command(message: Message):
    lang = await get_lang(message.from_user.id)
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        query = args[1].strip()
        await perform_search(message, query)
    else:
        SEARCHING_USERS.add(message.from_user.id)
        await message.answer(t("search_prompt", lang), parse_mode="HTML")


@router.message(F.text, _in_search_mode)
async def handle_text_message(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    SEARCHING_USERS.discard(user_id)
    await perform_search(message, text)


@router.message(F.text & ~F.text.startswith("/") & (F.chat.type == ChatType.PRIVATE))
async def fallback_plain_search(message: Message):
    if not message.text:
        return
    text = message.text.strip()
    if not text:
        return
    if text.lower().startswith("http://") or text.lower().startswith("https://"):
        return
    user_id = message.from_user.id
    SEARCHING_USERS.discard(user_id)
    await perform_search(message, text)


async def _song_results(user_id, lang, query, page):
    songs, total = await db.search_songs_page(query, page=page, per_page=PER_PAGE)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    if total == 0:
        return None, None, 0, 1
    header = t("search_results_header", lang, q=query, n=total)
    kb = search_results_kb(songs, lang, page=page, pages=pages)
    return header, kb, total, pages


async def perform_search(message: Message, query: str):
    lang = await get_lang(message.from_user.id)
    if not query:
        await message.answer(t("search_need_query", lang))
        return

    query = normalize_myanmar(query)

    artists = await db.search_artists(query)
    if artists:
        from keyboards.inline import artists_kb as _akb
        await message.answer(
            t("search_artists_header", lang, q=query, n=len(artists)),
            parse_mode="HTML",
            reply_markup=_akb(artists, lang),
        )
        return

    LAST_SEARCH[message.from_user.id] = query
    header, kb, total, pages = await _song_results(message.from_user.id, lang, query, 1)
    if total == 0:
        await message.answer(
            t("search_not_found", lang, q=query),
            reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS, lang),
        )
        return

    await message.answer(header, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("spage:"))
async def search_page(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    try:
        page = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer()
        return
    query = LAST_SEARCH.get(callback.from_user.id)
    if not query:
        await callback.answer(t("search_need_query", lang))
        return
    header, kb, total, pages = await _song_results(callback.from_user.id, lang, query, page)
    if total == 0:
        await callback.answer(t("search_not_found", lang, q=query))
        return
    try:
        await callback.message.edit_text(header, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


# ---------------- Inline mode (@bot <query>) ----------------
@router.inline_query()
async def inline_search(query: InlineQuery):
    user_id = query.from_user.id
    lang = await get_lang(user_id)
    q = (query.query or "").strip()

    # Admins with an empty query get the admin menu.
    if not q:
        if user_id in ADMIN_IDS:
            items = [
                ("admin_add_cat", "➕ အမျိုးအစား ထည့်", "အမျိုးအစားအသစ် ထပ်ထည့်ရန်", "category"),
                ("admin_upload", "⬆️ Album + သီချင်းတင်ရန်", "Album အသစ်နှင့် သီချင်းများ တင်ရန်", "upload album"),
                ("admin_add_song", "🎵 အယ်လ်ဘမ်ထဲ သီချင်းထည့်", "ရှိပြီးသား Album ထဲ သီချင်းထည့်ရန်", "song add"),
                ("admin_stats", "📊 စာရင်းဇယား", "စာရင်းဇယား ကြည့်ရန်", "stats"),
                ("admin_delete_menu", "🗑 ဖျက်ရန်", "သီချင်း / Album / အမျိုးအစား ဖျက်ရန်", "delete"),
            ]
            results = [
                InlineQueryResultArticle(
                    id=f"admin_{action}",
                    title=title,
                    description=desc,
                    input_message_content=InputTextMessageContent(
                        message_text=get_admin_panel_text(lang),
                        parse_mode="HTML",
                    ),
                    reply_markup=admin_main_kb(lang),
                )
                for action, title, desc, _kw in items
            ]
            await query.answer(results, is_personal=True, cache_time=0)
            return

        prompt = InlineQueryResultArticle(
            id="search_hint",
            title=t("search_inline_empty", lang),
            description=t("m_search", lang),
            input_message_content=InputTextMessageContent(message_text=t("m_search", lang)),
        )
        await query.answer([prompt], is_personal=True, cache_time=5)
        return

    normalized = normalize_myanmar(q)
    songs, _total = await db.search_songs_page(normalized, page=1, per_page=20)
    results = []
    for song in songs:
        title = song.get("title") or "—"
        artist_name = song.get("artist_name") or ""
        album_name = song.get("album_name") or ""
        desc = " • ".join(x for x in [artist_name, album_name] if x)
        caption = f"🎵 <b>{title}</b>"
        if artist_name:
            caption += f"\n🎤 {artist_name}"
        if album_name:
            caption += f"\n📀 {album_name}"
        results.append(
            InlineQueryResultCachedAudio(
                id=str(song["_id"]),
                audio_file_id=song["file_id"],
                title=title,
                description=desc or None,
                caption=caption,
                parse_mode="HTML",
            )
        )
    await query.answer(results, is_personal=True, cache_time=30)
