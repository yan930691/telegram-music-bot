from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb(is_admin=False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📀 အမျိုးအစားများ", callback_data="cats")
    builder.button(text="🎵 သီချင်းများ", callback_data="songs_all")
    builder.button(text="🔥 လူကြိုက်များ", callback_data="popular")
    builder.button(text="🔍 ရှာဖွေရန်", callback_data="search")
    if is_admin:
        builder.button(text="⚙️ အက်ဒမင် မီနူး", callback_data="admin_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def categories_kb(cats) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(
            text=f"🎵 {cat['name']}",
            callback_data=f"cat:{cat['_id']}",
        )
    builder.button(text="🔙 နောက်သို့", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def category_actions_kb(cat_id, is_admin=False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📀 အယ်လ်ဘမ်များ", callback_data=f"albums:{cat_id}")
    if is_admin:
        builder.button(text="➕ အယ်လ်ဘမ် ထည့်", callback_data=f"add_album:{cat_id}")
        builder.button(text="🗑 အမျိုးအစားဖျက်", callback_data=f"del_cat:{cat_id}")
    builder.button(text="🔙 နောက်သို့", callback_data="cats")
    builder.adjust(1)
    return builder.as_markup()


def albums_kb(albums, cat_id) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for album in albums:
        title = album["name"]
        if album.get("artist"):
            title += f" | {album['artist']}"
        builder.button(
            text=f"📀 {title}",
            callback_data=f"album:{album['_id']}",
        )
    builder.button(text="🔙 နောက်သို့", callback_data=f"cat:{cat_id}")
    builder.adjust(1)
    return builder.as_markup()


def album_actions_kb(album_id, is_admin=False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎵 သီချင်းများ", callback_data=f"songs:{album_id}")
    builder.button(text="📥 အယ်လ်ဘမ်အားလုံး ဒေါင်းလုဒ်", callback_data=f"dl_album:{album_id}")
    if is_admin:
        builder.button(text="➕ သီချင်းထည့်", callback_data=f"add_song:{album_id}")
        builder.button(text="🗑 အယ်လ်ဘမ် ဖျက်", callback_data=f"del_album:{album_id}")
    builder.button(text="🔙 နောက်သို့", callback_data="albums_back")
    builder.adjust(1)
    return builder.as_markup()


def songs_kb(songs, album_id) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, start=1):
        builder.button(
            text=f"🎵 {i}. {song['title']}",
            callback_data=f"song:{song['_id']}",
        )
    builder.button(text="📥 အယ်လ်ဘမ်အားလုံး ဒေါင်းလုဒ်", callback_data=f"dl_album:{album_id}")
    builder.button(text="🔙 နောက်သို့", callback_data=f"album:{album_id}")
    builder.adjust(1)
    return builder.as_markup()


def album_songs_to_send(album_id, songs) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, start=1):
        builder.button(
            text=f"{i}. {song['title']}",
            callback_data=f"send_song:{song['_id']}",
        )
    builder.button(text="❌ ပိတ်မည်", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def back_to_cats_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 နောက်သို့", callback_data="cats")
    return builder.as_markup()


def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ အမျိုးအစား ထည့်", callback_data="admin_add_cat")
    builder.button(text="➕ အယ်လ်ဘမ် ထည့်", callback_data="admin_add_album")
    builder.button(text="🎵 သီချင်းထည့်", callback_data="admin_add_song")
    builder.button(text="📊 စာရင်းဇယား", callback_data="admin_stats")
    builder.button(text="🗑 ဖျက်ရန်", callback_data="admin_delete_menu")
    builder.button(text="🔙 နောက်သို့", callback_data="back_main")
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()


def admin_delete_menu_kb(cats) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(
            text=f"🗑 {cat['name']}",
            callback_data=f"del_cat:{cat['_id']}",
        )
    builder.button(text="🔙 နောက်သို့", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def album_add_cat_kb(cats) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(
            text=f"📀 {cat['name']}",
            callback_data=f"albadd_cat:{cat['_id']}",
        )
    builder.button(text="🔙 နောက်သို့", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def search_results_kb(songs) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, start=1):
        builder.button(
            text=f"🎵 {i}. {song['title']}",
            callback_data=f"song:{song['_id']}",
        )
    builder.button(text="🔙 နောက်သို့", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def popular_songs_kb(songs) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, start=1):
        builder.button(
            text=f"🔥 {i}. {song['title']} (ဒေါင်းလုဒ်: {song.get('downloads', 0)})",
            callback_data=f"song:{song['_id']}",
        )
    builder.button(text="🔙 နောက်သို့", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()
