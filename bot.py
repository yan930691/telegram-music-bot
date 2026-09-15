import asyncio
import logging
import os

from aiohttp import web
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
    ConversationHandler,
)
from config import BOT_TOKEN, ADMIN_IDS
from database import db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ALBUM_NAME, ARTIST, YEAR, COVER, SONGS = range(5)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 Albums", callback_data="albums")],
        [InlineKeyboardButton("🔍 Search Music", callback_data="search_help")],
    ]
    if is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin", callback_data="admin")])

    await update.message.reply_text(
        "🎵 <b>MYANMAR MUSIC LIBRARY</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "မင်္ဂလာပါ 👋\n\n"
        "မြန်မာသီချင်းများကို Album အလိုက် ရှာဖွေနားဆင်နိုင်ပါတယ်။\n\n"
        "👇 အောက်က Menu မှာ ရွေးချယ်ပါ။",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def show_albums(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    albums = db.get_all_albums()

    if not albums:
        await query.edit_message_text(
            "📚 <b>Albums</b>\n\nလောလောဆယ် Album မရှိသေးပါဘူး။",
            parse_mode="HTML",
        )
        return

    keyboard = []
    for album in albums:
        name = album.get("album_name", "Unknown Album")
        artist = album.get("artist", "")
        text = f"💿 {name}" + (f" — {artist}" if artist else "")
        keyboard.append([InlineKeyboardButton(text, callback_data=f"album:{album['_id']}")])

    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
    await query.edit_message_text(
        "📚 <b>ALBUM COLLECTION</b>\n━━━━━━━━━━━━━━━━━━\n\n💿 Album တစ်ခုကို ရွေးပါ။",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def show_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    album_id = query.data.split(":", 1)[1]
    album = db.get_album(album_id)

    if not album:
        await query.edit_message_text("❌ Album မတွေ့ပါ။")
        return

    name = album.get("album_name", "Unknown Album")
    artist = album.get("artist", "")
    year = album.get("year", "")
    songs = album.get("songs", [])

    text = f"💿 <b>{name}</b>\n👤 {artist}\n"
    if year:
        text += f"📅 {year}\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    if not songs:
        text += "🎵 သီချင်းမရှိသေးပါ။"

    keyboard = []
    for index, song in enumerate(songs):
        title = song.get("title", "Unknown Song")
        keyboard.append([
            InlineKeyboardButton(
                f"🎵 {title}",
                callback_data=f"song:{album_id}:{index}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("📥 Download All", callback_data=f"download_all:{album_id}")
    ])
    keyboard.append([
        InlineKeyboardButton("◀️ Albums", callback_data="albums"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])

    cover = album.get("cover_file_id")
    try:
        await query.message.delete()
    except Exception:
        pass

    if cover:
        await query.message.chat.send_photo(
            photo=cover,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
    else:
        await query.message.chat.send_message(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

async def send_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    album_id = parts[1]
    song_index = int(parts[2])
    song = db.get_song(album_id, song_index)

    if not song:
        await query.answer("❌ သီချင်းမတွေ့ပါ။", show_alert=True)
        return

    file_id = song.get("file_id")
    title = song.get("title", "Unknown Song")

    if not file_id:
        await query.answer("❌ Music file မရှိပါ။", show_alert=True)
        return

    await query.message.chat.send_audio(
        audio=file_id,
        caption=f"🎵 <b>{title}</b>\n\n🎧 Myanmar Music Library",
        parse_mode="HTML",
    )

async def download_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    album_id = query.data.split(":", 1)[1]
    album = db.get_album(album_id)

    if not album:
        return

    songs = album.get("songs", [])
    if not songs:
        await query.answer("သီချင်းမရှိသေးပါ။", show_alert=True)
        return

    await query.message.chat.send_message(
        f"📥 <b>{album.get('album_name')}</b>\n"
        f"🎵 သီချင်း {len(songs)} ပုဒ်ရှိပါတယ်။\n\n"
        "Download စတင်ပါပြီ...",
        parse_mode="HTML",
    )

    for song in songs:
        file_id = song.get("file_id")
        title = song.get("title", "Unknown Song")
        if file_id:
            try:
                await query.message.chat.send_audio(
                    audio=file_id,
                    caption=f"🎵 <b>{title}</b>",
                    parse_mode="HTML",
                )
            except Exception as error:
                logger.error("Failed to send song: %s", error)

async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📚 Albums", callback_data="albums")],
        [InlineKeyboardButton("🔍 Search Music", callback_data="search_help")],
    ]
    if is_admin(query.from_user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin", callback_data="admin")])

    await query.edit_message_text(
        "🎵 <b>MYANMAR MUSIC LIBRARY</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "မြန်မာသီချင်းများကို ရှာဖွေပြီး Download လုပ်နိုင်ပါတယ်။",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def search_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔍 <b>SEARCH MUSIC</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        "သီချင်းနာမည်၊ အဆိုတော်၊ Album နာမည်တစ်ခုခုကို ရိုက်ပြီး ပို့ပါ။\n\n"
        "ဥပမာ — <code>ချစ်သူ</code>\n"
        "<code>စိုင်းထီးဆိုင်</code>",
        parse_mode="HTML",
    )

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if not q:
        return
    results = db.search_songs(q)

    if not results:
        await update.message.reply_text(
            "🔍 <b>မတွေ့ပါ။</b>\n\nအခြား သီချင်းနာမည် သို့မဟုတ် အဆိုတော်နာမည်နဲ့ ပြန်ရှာကြည့်ပါ။",
            parse_mode="HTML",
        )
        return

    keyboard = []
    for item in results[:50]:
        text = f"🎵 {item['title']}"
        if item["artist"]:
            text += f" — {item['artist']}"
        keyboard.append([
            InlineKeyboardButton(
                text,
                callback_data=f"song:{item['album_id']}:{item['song_index']}"
            )
        ])

    await update.message.reply_text(
        f"🔎 <b>Search Results</b>\n\n"
        f"ရှာဖွေမှု — <code>{q}</code>\n\n"
        f"တွေ့ရှိမှု — {len(results)} ပုဒ်",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Admin only.", show_alert=True)
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Album", callback_data="add_album")],
        [InlineKeyboardButton("📚 View Albums", callback_data="albums")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ]
    await query.edit_message_text(
        "⚙️ <b>ADMIN PANEL</b>\n━━━━━━━━━━━━━━━━━━\n\nAdmin function တစ်ခုရွေးပါ။",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def add_album_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    context.user_data.clear()
    await query.message.reply_text("➕ <b>ADD NEW ALBUM</b>\n\n💿 Album Name ကို ပို့ပါ။", parse_mode="HTML")
    return ALBUM_NAME

async def add_album_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["album_name"] = update.message.text.strip()
    await update.message.reply_text("👤 Artist Name ကို ပို့ပါ။")
    return ARTIST

async def add_album_artist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["artist"] = update.message.text.strip()
    await update.message.reply_text("📅 Album Year ကို ပို့ပါ။ မရှိရင် - လို့ ပို့ပါ။")
    return YEAR

async def add_album_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = update.message.text.strip()
    context.user_data["year"] = "" if year == "-" else year
    await update.message.reply_text("📸 Album Cover ပုံကို ပို့ပါ။")
    return COVER

async def add_album_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ ပုံကို Photo အနေနဲ့ ပို့ပါ။")
        return COVER

    context.user_data["cover_file_id"] = update.message.photo[-1].file_id

    album_id = db.create_album(
        context.user_data["album_name"],
        context.user_data["artist"],
        context.user_data["year"],
        context.user_data["cover_file_id"],
    )
    context.user_data["album_id"] = album_id

    await update.message.reply_text(
        "✅ <b>Album Created!</b>\n\n"
        "အခု Music File တွေကို ပို့ပါ။\n\n"
        "🎵 <b>Audio Caption ထဲမှာ သီချင်းနာမည်ထည့်ပေးပါ။</b>\n\n"
        "ပြီးရင် /done လို့ ပို့ပါ။",
        parse_mode="HTML",
    )
    return SONGS

async def add_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    if not update.message.audio:
        await update.message.reply_text("❌ Audio file ကို ပို့ပါ။")
        return SONGS

    audio = update.message.audio
    title = (
        update.message.caption
        or audio.title
        or audio.file_name
        or "Unknown Song"
    ).strip()

    success = db.add_song(
        context.user_data["album_id"],
        title,
        audio.file_id,
        audio.duration or 0,
    )

    await update.message.reply_text(
        f"✅ <b>{title}</b>\n"
        "Album ထဲထည့်ပြီးပါပြီ။\n\n"
        "နောက်သီချင်းကို ဆက်ပို့ပါ။ ပြီးရင် /done",
        parse_mode="HTML",
    ) if success else await update.message.reply_text("❌ Song ထည့်ရာမှာ error ဖြစ်ပါတယ်။")

    return SONGS

async def add_album_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ <b>Album Setup Complete!</b>\n\n"
        "📚 Album ကို MongoDB ထဲမှာ သိမ်းပြီးပါပြီ။",
        parse_mode="HTML",
    )
    return ConversationHandler.END

async def cancel_add_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Add Album ကို Cancel လုပ်လိုက်ပါပြီ။")
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=context.error)


# ---------------- Render web service keep-alive ----------------

async def health_handler(request: web.Request):
    return web.Response(text="OK")


async def _keepalive_loop():
    """Ping our own health URL periodically to stop Render free tier sleeping."""
    url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not url:
        logger.info("RENDER_EXTERNAL_URL not set; keep-alive disabled.")
        return
    session = aiohttp.ClientSession()
    try:
        while True:
            await asyncio.sleep(240)
            try:
                async with session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    await resp.text()
            except Exception as e:
                logger.info("Keep-alive ping failed: %s", e)
    finally:
        await session.close()


async def _start_web_server():
    port = int(os.getenv("PORT", 8000))
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health server listening on :%s", port)


def main():
    logger.info("Checking MongoDB connection...")
    if not db.ping():
        logger.error("MongoDB connection failed.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_album_start, pattern=r"^add_album$")],
        states={
            ALBUM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_album_name)],
            ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_album_artist)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_album_year)],
            COVER: [MessageHandler(filters.PHOTO, add_album_cover)],
            SONGS: [MessageHandler(filters.AUDIO, add_song)],
        },
        fallbacks=[
            CommandHandler("done", add_album_done),
            CommandHandler("cancel", cancel_add_album),
        ],
    )

    application.add_handler(conversation)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("done", add_album_done))
    application.add_handler(CommandHandler("cancel", cancel_add_album))

    application.add_handler(CallbackQueryHandler(show_albums, pattern=r"^albums$"))
    application.add_handler(CallbackQueryHandler(show_album, pattern=r"^album:"))
    application.add_handler(CallbackQueryHandler(send_song, pattern=r"^song:"))
    application.add_handler(CallbackQueryHandler(download_all, pattern=r"^download_all:"))
    application.add_handler(CallbackQueryHandler(home, pattern=r"^home$"))
    application.add_handler(CallbackQueryHandler(search_help, pattern=r"^search_help$"))
    application.add_handler(CallbackQueryHandler(admin_menu, pattern=r"^admin$"))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, search_music)
    )

    application.add_error_handler(error_handler)

    logger.info("🎵 Myanmar Music Bot started.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_start_web_server())
        loop.create_task(_keepalive_loop())
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.start())
        loop.run_until_complete(application.updater.start_polling())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(application.updater.stop())
        loop.run_until_complete(application.stop())

if __name__ == "__main__":
    main()
