from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.i18n import t, DEFAULT_LANG


def main_menu_kb(is_admin=False, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("m_cats", lang), callback_data="cats")
    builder.button(text=t("m_artists", lang), callback_data="artists_all")
    builder.button(text=t("m_songs", lang), callback_data="songs_all")
    builder.button(text=t("m_popular", lang), callback_data="popular")
    builder.button(text=t("m_new", lang), callback_data="songs_new")
    builder.button(text=t("m_search", lang), callback_data="search")
    builder.button(text=t("m_settings", lang), callback_data="settings")
    if is_admin:
        builder.button(text=t("m_admin", lang), callback_data="admin_menu")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def settings_kb(lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇲🇲 မြန်မာ", callback_data="setlang:my")
    builder.button(text="🇬🇧 English", callback_data="setlang:en")
    builder.button(text=t("back", lang), callback_data="back_main")
    builder.adjust(2, 1)
    return builder.as_markup()


def artists_kb(artists, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for artist in artists:
        builder.button(
            text=f"🎤 {artist['name']}",
            callback_data=f"artist:{artist['_id']}",
        )
    builder.button(text=t("back", lang), callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def categories_kb(cats, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(
            text=f"🎵 {cat['name']}",
            callback_data=f"cat:{cat['_id']}",
        )
    builder.button(text=t("back", lang), callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def category_actions_kb(cat_id, is_admin=False, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_cat_albums", lang), callback_data=f"albums:{cat_id}")
    if is_admin:
        builder.button(text=t("btn_add_album", lang), callback_data=f"add_album:{cat_id}")
        builder.button(text=t("btn_del_cat", lang), callback_data=f"del_cat:{cat_id}")
    builder.button(text=t("back", lang), callback_data="cats")
    builder.adjust(1)
    return builder.as_markup()


def albums_kb(albums, cat_id, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for album in albums:
        title = album["name"]
        if album.get("artist"):
            title += f" | {album['artist']}"
        builder.button(
            text=f"📀 {title}",
            callback_data=f"album:{album['_id']}",
        )
    builder.button(text=t("back", lang), callback_data=f"cat:{cat_id}")
    builder.adjust(1)
    return builder.as_markup()


def artist_albums_kb(albums, artist_id, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for album in albums:
        title = album["name"]
        builder.button(
            text=f"📀 {title}",
            callback_data=f"album:{album['_id']}",
        )
    builder.button(text=t("back", lang), callback_data=f"artist:{artist_id}")
    builder.adjust(1)
    return builder.as_markup()


def album_actions_kb(album_id, is_admin=False, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_album_songs", lang), callback_data=f"songs:{album_id}")
    builder.button(text=t("btn_album_download_all", lang), callback_data=f"dl_album:{album_id}")
    if is_admin:
        builder.button(text=t("btn_add_song", lang), callback_data=f"add_song:{album_id}")
        builder.button(text=t("btn_move_cat", lang), callback_data=f"move_album:{album_id}")
        builder.button(text=t("btn_del_album", lang), callback_data=f"del_album:{album_id}")
    builder.button(text=t("back", lang), callback_data="albums_back")
    builder.adjust(1)
    return builder.as_markup()


def move_album_cat_kb(album_id, cats, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(
            text=f"📂 {cat['name']}",
            callback_data=f"movecat:{album_id}:{cat['_id']}",
        )
    builder.button(text=t("back", lang), callback_data=f"album:{album_id}")
    builder.adjust(1)
    return builder.as_markup()


def songs_kb(songs, album_id, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, start=1):
        num = song.get("track_no") or i
        builder.button(
            text=f"🎵 {num}. {song['title']}",
            callback_data=f"song:{song['_id']}",
        )
    builder.button(text=t("btn_album_download_all", lang), callback_data=f"dl_album:{album_id}")
    builder.button(text=t("back", lang), callback_data=f"album:{album_id}")
    builder.adjust(1)
    return builder.as_markup()


def album_songs_to_send(album_id, songs, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, start=1):
        num = song.get("track_no") or i
        builder.button(
            text=f"{num}. {song['title']}",
            callback_data=f"send_song:{song['_id']}",
        )
    builder.button(text=t("close_btn", lang), callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def back_to_cats_kb(lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("back", lang), callback_data="cats")
    return builder.as_markup()


def admin_main_kb(lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ အမျိုးအစား ထည့်" if lang == "my" else "➕ Add Category",
                   callback_data="admin_add_cat")
    builder.button(text="⬆️ Album + သီချင်းတင်ရန်" if lang == "my" else "⬆️ Upload Album + Songs",
                   callback_data="admin_upload")
    builder.button(text="🎵 အယ်လ်ဘမ်ထဲ သီချင်းထည့်" if lang == "my" else "🎵 Add Song to Album",
                   callback_data="admin_add_song")
    builder.button(text="📊 စာရင်းဇယား" if lang == "my" else "📊 Statistics",
                   callback_data="admin_stats")
    builder.button(text="🗑 ဖျက်ရန်" if lang == "my" else "🗑 Delete",
                   callback_data="admin_delete_menu")
    builder.button(text=t("back", lang), callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def upload_cat_kb(cats, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(
            text=f"📀 {cat['name']}",
            callback_data=f"upcat:{cat['_id']}",
        )
    builder.button(text=t("back", lang), callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def upload_batch_kb(lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("a_upload_finish_btn", lang), callback_data="finish_upload")
    builder.button(text=t("a_upload_cancel_btn", lang), callback_data="cancel_upload")
    builder.button(text=t("admin_menu_btn", lang), callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_delete_menu_kb(cats, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(
            text=f"🗑 {cat['name']}",
            callback_data=f"del_cat:{cat['_id']}",
        )
    builder.button(text=t("back", lang), callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_delete_choice_kb(lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("a_del_btn_song", lang), callback_data="del_pick_song")
    builder.button(text=t("a_del_btn_album", lang), callback_data="del_pick_album")
    builder.button(text=t("a_del_btn_cat", lang), callback_data="del_pick_cat")
    builder.button(text=t("back", lang), callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_album_delete_kb(albums, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, album in enumerate(albums, start=1):
        text = f"📀 {i}. {album['name']}"
        if album.get("artist"):
            text += f" — {album['artist']}"
        builder.button(
            text=text,
            callback_data=f"del_album:{album['_id']}",
        )
    builder.button(text=t("back", lang), callback_data="admin_delete_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_song_delete_kb(songs, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, start=1):
        builder.button(
            text=f"🎵 {i}. {song['title']}",
            callback_data=f"del_song:{song['_id']}",
        )
    builder.button(text=t("back", lang), callback_data="admin_delete_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_confirm_delete_kb(data, back_data, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("confirm_yes", lang), callback_data=f"confirm_{data}")
    builder.button(text=t("confirm_no", lang), callback_data=back_data)
    builder.adjust(2)
    return builder.as_markup()


def album_add_cat_kb(cats, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(
            text=f"📀 {cat['name']}",
            callback_data=f"albadd_cat:{cat['_id']}",
        )
    builder.button(text=t("back", lang), callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def album_added_kb(album_id, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("a_btn_add_songs_here", lang), callback_data=f"add_song:{album_id}")
    builder.button(text=t("a_btn_view_album", lang), callback_data=f"album:{album_id}")
    builder.button(text=t("admin_menu_btn", lang), callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def song_added_kb(album_id, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("a_btn_next_song", lang), callback_data=f"add_song:{album_id}")
    builder.button(text=t("admin_menu_btn", lang), callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def adding_songs_kb(album_id, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("a_btn_finish", lang), callback_data=f"finish_songs:{album_id}")
    builder.button(text=t("a_btn_delete_batch", lang), callback_data="cancel_batch")
    builder.button(text=t("admin_menu_btn", lang), callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def search_results_kb(songs, lang=DEFAULT_LANG, page=1, pages=1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    offset = (page - 1) * 8
    for i, song in enumerate(songs, start=1):
        builder.button(
            text=f"🎵 {offset + i}. {song['title']}",
            callback_data=f"song:{song['_id']}",
        )
    if pages > 1:
        if page > 1:
            builder.button(text=t("btn_prev_page", lang), callback_data=f"spage:{page - 1}")
        builder.button(text=t("page_indicator", lang, page=page, pages=pages), callback_data="noop")
        if page < pages:
            builder.button(text=t("btn_next_page", lang), callback_data=f"spage:{page + 1}")
    builder.button(text=t("back", lang), callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def popular_songs_kb(songs, lang=DEFAULT_LANG) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, start=1):
        builder.button(
            text=f"🔥 {i}. {song['title']} {t('dl_count_short', lang, n=song.get('downloads', 0))}",
            callback_data=f"song:{song['_id']}",
        )
    builder.button(text=t("back", lang), callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()
