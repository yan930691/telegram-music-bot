# -*- coding: utf-8 -*-
"""Minimal i18n layer for the music bot (Myanmar / English).

Usage:
    from utils.i18n import t, get_lang, set_lang
    lang = await get_lang(user_id)
    await message.answer(t("welcome", lang))
"""

DEFAULT_LANG = "my"
SUPPORTED = ("my", "en")
LANG_NAMES = {"my": "မြန်မာ", "en": "English"}

# In-memory cache so we don't hit Mongo on every callback.
_LANG_CACHE = {}

TRANSLATIONS = {
    "my": {
        # -------- common --------
        "back": "🔙 နောက်သို့",
        "close_btn": "❌ ပိတ်မည်",
        "closed": "❌ ပိတ်လိုက်ပါပြီ",
        "admin_menu_btn": "🏠 အက်ဒမင် မီနူး",
        "not_admin": "❌ အက်ဒမင် မဟုတ်ပါ!",
        "not_admin_short": "❌ သင်သည် အက်ဒမင် မဟုတ်ပါ။",
        "error_generic": "⚠️ အမှားဖြစ်သွားသည်။",
        "song_not_found": "❌ သီချင်းမတွေ့ပါ!",
        "sent_ok": "🎵 ပို့လိုက်ပါပြီ!",
        "deleted_ok": "🗑 ဖျက်ပြီးပါပြီ!",
        "cancel_label": "❌ ရပ်လိုက်မည်",
        "confirm_yes": "✅ ဖျက်မည်",
        "confirm_no": "❌ မဖျက်တော့",

        # -------- welcome --------
        "welcome": (
            "🎵 <b>ဂီတ Bot</b> မှ ကြိုဆိုပါတယ်! 🌟\n\n"
            "ဤ bot တွင် သင်နှစ်သက်သော သီချင်းများကို "
            "အလွယ်တကူ ရှာဖွေ နားထောင် ဒေါင်းလုဒ် လုပ်နိုင်ပါသည်။\n\n"
            "⬇️ အောက်ပါ ခလုတ်များမှတစ်ဆင့် စတင်အသုံးပြုနိုင်ပါသည်:"
        ),
        "help": (
            "🆘 <b>အကူအညီ</b>\n\n"
            "🎵 <b>Bot အသုံးပြုနည်း:</b>\n"
            "• 📀 သီချင်းအမျိုးအစားများ — အမျိုးအစားအလိုက် Album ရွေးနိုင်သည်\n"
            "• 🎤 အနုပညာရှင်များ — အဆိုတော်ရွေးပါက ၎င်း၏ Album အားလုံး ပြပါသည်\n"
            "• သီချင်းကို နှိပ်လိုက်ရင် bot က chat ထဲ ပို့ပေးပါသည်\n"
            "• 🔍 ရှာဖွေ ခလုတ်ဖြင့် အဆိုတော် / သီချင်းအမည် ရိုက်ပြီး ရှာဖွေနိုင်သည်\n"
            "• 💬 မည်သည့် chat တွင်မဆို <code>@{bot} သီချင်းအမည်</code> ရိုက်ပြီး ရှာနိုင်သည်\n"
            "• ⚙️ ဆက်တင် — ဘာသာစကား (မြန်မာ/English) ပြောင်းနိုင်သည်\n\n"
            "<b>Command များ:</b>\n"
            "/start - စတင်ခြင်း\n"
            "/help - အကူအညီ\n"
            "/menu - အဓိက မီနူး\n"
            "/search &lt;အမည်&gt; - အဆိုတော် / သီချင်း ရှာဖွေရန်\n"
            "/admin - (အက်ဒမင်) စီမံခန့်ခွဲရန်\n"
            "/upload - (အက်ဒမင်) Album + သီချင်း သွင်းရန်"
        ),
        "admin_panel": (
            "⚙️ <b>အက်ဒမင် မီနူး</b>\n\n"
            "အောက်ပါ လုပ်ဆောင်ချက်များ ပြုလုပ်နိုင်ပါသည်:\n\n"
            "➕ အမျိုးအစား / အယ်လ်ဘမ် / သီချင်း ထည့်ခြင်း\n"
            "🗑 ဖျက်ခြင်း\n"
            "📊 စာရင်းဇယားကြည့်ခြင်း"
        ),

        # -------- main menu --------
        "m_cats": "📀 သီချင်းအမျိုးအစားများ",
        "m_artists": "🎤 အနုပညာရှင်များ",
        "m_songs": "🎵 သီချင်းများ",
        "m_popular": "🔥 လူကြိုက်များ",
        "m_new": "🆕 အသစ်များ",
        "m_search": "🔍 ရှာဖွေရန်",
        "m_admin": "⚙️ အက်ဒမင် မီနူး",
        "m_settings": "⚙️ ဆက်တင်",

        # -------- settings --------
        "settings_title": "⚙️ <b>ဆက်တင်</b>\n\n🌐 ဘာသာစကား ရွေးပါ:",
        "lang_label": "🌐 ဘာသာစကား",
        "lang_set": "✅ ဘာသာစကား ပြောင်းပြီးပါပြီ: <b>{name}</b>",

        # -------- categories --------
        "cats_header": "📂 <b>သီချင်းအမျိုးအစားများ ရွေးချယ်ပါ:</b>",
        "cats_empty": "📂 သီချင်းအမျိုးအစားများ မရှိသေးပါ။",
        "cat_actions_hint": "အောက်ပါ လုပ်ဆောင်ချက်များ ရွေးချယ်ပါ:",
        "btn_cat_albums": "📀 အယ်လ်ဘမ်များ",
        "btn_add_album": "➕ အယ်လ်ဘမ် ထည့်",
        "btn_del_cat": "🗑 အမျိုးအစားဖျက်",

        # -------- albums --------
        "albums_header": "📀 <b>အယ်လ်ဘမ်များ:</b>",
        "albums_empty": "📂 အယ်လ်ဘမ် မရှိသေးပါ!",
        "album_dl_label": "📥 ဒေါင်းလုဒ်: {n}",
        "album_actions_hint": "လုပ်ဆောင်ချက် ရွေးချယ်ပါ:",
        "btn_album_songs": "🎵 သီချင်းများ",
        "btn_album_download_all": "📥 အယ်လ်ဘမ်အားလုံး ဒေါင်းလုဒ်",
        "btn_add_song": "➕ သီချင်းထည့်",
        "btn_move_cat": "📂 အမျိုးအစား ပြောင်း",
        "btn_del_album": "🗑 အယ်လ်ဘမ် ဖျက်",

        # -------- songs --------
        "songs_header": "🎵 <b>သီချင်းများ ({n}):</b>",
        "songs_empty": "🎵 သီချင်းမရှိသေးပါ!",
        "dl_album_header": "📀 <b>အယ်လ်ဘမ်ထဲမှ သီချင်းများ ({n})</b>\n\nပို့စေချင်သော သီချင်းကို ရွေးပါ:",
        "dl_count_short": "(ဒေါင်းလုဒ်: {n})",

        # -------- artists --------
        "artists_header": "🎤 <b>အနုပညာရှင်များ ({n}):</b>\n\nအဆိုတော် ရွေးပါက ၎င်း၏ အယ်လ်ဘမ်များ ပြပါမည်:",
        "artists_empty": "🎤 အနုပညာရှင် မရှိသေးပါ!",
        "artist_header": "🎤 <b>{name}</b>\n📀 အယ်လ်ဘမ်: {n}\n\nအယ်လ်ဘမ် ရွေးပါ:",
        "artist_albums_empty": "📀 ဤအနုပညာရှင်အတွက် အယ်လ်ဘမ် မရှိသေးပါ!",

        # -------- search --------
        "search_prompt": (
            "🔍 <b>ရှာဖွေရန် အဆိုတော် သို့မဟုတ် သီချင်းအမည် ရိုက်ထည့်ပါ:</b>\n\n"
            "ဥပမာ: <code>ချစ်</code> သို့မဟုတ် <code>အိုင်</code>"
        ),
        "search_need_query": "❌ ရှာဖွေရန် အမည် ထည့်ပါ။",
        "search_not_found": "😔 '{q}' နှင့် ကိုက်ညီသော သီချင်း မတွေ့ပါ။\nအခြားအမည် စမ်းကြည့်ပါ။",
        "search_results_header": "🔍 <b>'{q}' အတွက် ရလဒ် ({n}):</b>",
        "search_artists_header": "🔍 <b>'{q}' အတွက် အနုပညာရှင် ({n}):</b>",
        "btn_next_page": "ရှေ့သို့ ▶️",
        "btn_prev_page": "◀️ နောက်သို့",
        "page_indicator": "📄 စာမျက်နှာ {page}/{pages}",
        "search_inline_empty": "ရှာဖွေရန် အမည် ရိုက်ပါ",

        # -------- popular / new --------
        "popular_header": "🔥 <b>လူကြိုက်များသော သီချင်းများ (ထိပ်တန်း 10):</b>",
        "popular_empty": "🔥 လူကြိုက်များသော သီချင်း မရှိသေးပါ!",
        "new_header": "🆕 <b>အသစ်ထည့်ထားသော သီချင်းများ (နောက်ဆုံး 10):</b>",
        "new_empty": "🆕 ထည့်သွင်းထားသော သီချင်း မရှိသေးပါ!",

        # -------- stats --------
        "stats_header": "📊 <b>စာရင်းဇယား:</b>",
        "stats_songs": "🎵 သီချင်းများ: <b>{n}</b>",
        "stats_albums": "📀 အယ်လ်ဘမ်များ: <b>{n}</b>",
        "stats_users": "👥 အသုံးပြုသူများ: <b>{n}</b>",
        "version_info": (
            "⚙️ <b>Bot Build</b>\n\n"
            "🆕 Version: <code>{ver}</code>\n"
            "🎵 သီချင်း: {songs}\n"
            "📀 အယ်လ်ဘမ်: {albums}\n"
            "👥 အသုံးပြုသူ: {users}"
        ),

        # -------- channel --------
        "ch_saved": "✅ <b>သီချင်းအသစ် ရောက်ရှိပါပြီ!</b>\n\n🎧 {title}\n🎤 {artist}\n📀 {album}\n\n🤖 Bot မှ ရယူလိုပါက bot chat သို့ ဝင်ရောက်ပါ",
        "ch_duplicate": "ℹ️ ဤသီချင်းကို သိမ်းပြီးသား ဖြစ်ပါသည်။",
        "announce_new": "🆕 <b>သီချင်းအသစ် ရောက်ရှိသည်</b>\n\n🎵 {n} ပုဒ် — 🎤 {artists}\n🎧 Bot ၌ နားထောင်နိုင်ပါပြီ",

        # -------- admin: general --------
        "a_nothing_pending": "⚠️ သီချင်း မပို့ရသေးပါ!",
        "a_no_flow": "ℹ️ လက်ရှိ တင်နေသည့် flow မရှိပါ။",
        "a_bf_start": "🌐 ရှိပြီးသား သီချင်းများကို English ⇄ မြန်မာ ဘာသာပြန်နေပါသည်... ခဏစောင့်ပါ။",
        "a_bf_progress": "🌐 ဘာသာပြန်နေသည်... ({n} ပုဒ် ပြီး)",
        "a_bf_done": "✅ ဘာသာပြန် backfill ပြီးပါပြီ — {n} ပုဒ် update လုပ်ခဲ့သည်။",
        "a_bf_none": "ℹ️ ဘာသာပြန်ရန် ကျန်သီချင်း မရှိပါ (အားလုံး ပြီးသားဖြစ်သည်)။",
        "a_bf_failed": "❌ ဘာသာပြန် မအောင်မြင်ပါ: {err}",
        "a_imp_no_channel": "⚠️ CHANNEL_ID မသတ်မှတ်ထားပါ။",
        "a_imp_no_creds": "⚠️ TG_API_ID / TG_API_HASH မသတ်မှတ်ရသေးပါ။\nmy.telegram.org မှ api_id/api_hash ယူပြီး Render Environment တွင် ထည့်ပါ။",
        "a_imp_start": "📥 ချန်နယ်ထဲက သီချင်းများကို bot ထဲ စတင် import လုပ်နေပါသည်... ခဏစောင့်ပါ။",
        "a_imp_progress": "📥 Import လုပ်နေသည်... ({scanned}/{total} | အသစ် {added} | ကျော် {skipped})",
        "a_imp_done": "✅ Import ပြီးပါပြီ။\nစစ်ခဲ့သည်: {scanned}\nအသစ်ထည့်: {added}\nအစားထိုး: {replaced}\nကျော်(ရှိပြီး): {skipped}",
        "a_imp_failed": "❌ Import မအောင်မြင်ပါ: {err}",
        "a_imp_peer_hint": "💡 Bot က သီးသန့် (private) ချန်နယ်ရဲ့ နံပါတ် id နဲ့ history ကို မဖတ်နိုင်ပါ။ CHANNEL_ID ကို ချန်နယ်ရဲ့ @username ပုံစံ ပြောင်းထည့်ပြီး ပြန်စမ်းပါ (ချန်နယ်ကို public လုပ်ထားရပါမယ်)။",
        "a_imp_need_post": "📮 ဒီ private ချန်နယ်ကို bot က အခုထိ မမြင်ဖူးသေးလို့ id ကို resolve မလုပ်နိုင်သေးပါ။ <b>ချန်နယ်ထဲ စာတစ်စောင် (ဘာပဲဖြစ်ဖြစ်) ပို့ပေးပါ</b> — bot က စက္ကန့် ၉၀ အထိ စောင့်နေပါတယ်။",
        "a_imp_need_forward": "📮 To resolve a private channel's id, <b>forward any single message from that channel to me</b>. Then run /importchannel again.",
        "a_imp_forward_ok": "✅ Forward received. Run /importchannel again to start import.",
        "a_add_cat_prompt": "➕ <b>အမျိုးအစား အမည် ရိုက်ထည့်ပါ:</b>",
        "a_add_cat_empty": "⚠️ ဦးစွာ အမျိုးအစားတစ်ခု ထည့်ပါ!",
        "a_choose_album_cat": "📀 <b>အယ်လ်ဘမ် ထည့်မည့် အမျိုးအစား ရွေးပါ:</b>",
        "a_add_song_first_cat": "⚠️ အရင်ဆုံး အမျိုးအစားတစ်ခု ထည့်ပါ!",
        "a_choose_song_cat": "🎵 <b>သီချင်းထည့်မည့် အမျိုးအစား ရွေးပါ:</b>",
        "a_no_album_in_cat": "⚠️ ဤအမျိုးအစားတွင် အယ်လ်ဘမ် မရှိပါ!",
        "a_choose_song_album": "📀 <b>သီချင်းထည့်မည့် အယ်လ်ဘမ် ရွေးပါ:</b>",
        "a_delete_choose": "🗑 <b>ဖျက်လိုသည့် အမျိုးအစား ရွေးပါ:</b>",
        "a_del_btn_song": "🗑 သီချင်းဖျက်",
        "a_del_btn_album": "🗑 Album ဖျက်",
        "a_del_btn_cat": "🗑 အမျိုးအစားဖျက်",
        "a_del_no_cat": "⚠️ ဖျက်ရန် အမျိုးအစား မရှိပါ!",
        "a_del_choose_cat": "🗑 <b>ဖျက်မည့် အမျိုးအစား ရွေးပါ:</b>",
        "a_del_no_album": "⚠️ ဖျက်ရန် Album မရှိပါ!",
        "a_del_choose_album": "🗑 <b>ဖျက်မည့် Album ရွေးပါ:</b>\n\n(Album ဖျက်လျှင် ထဲမှ သီချင်းများလည်း ပါ ဖျက်ပါမည်)",
        "a_del_no_song": "⚠️ ဖျက်ရန် သီချင်း မရှိပါ!",
        "a_del_choose_song": "🗑 <b>ဖျက်မည့် သီချင်း ရွေးပါ:</b>",
        "a_del_album_confirm": "⚠️ <b>{name}</b> ကို ဖျက်မည်လား?\n\nထဲမှ သီချင်း <b>{n}</b> ပုဒ်လည်း ပါ ဖျက်ပါမည်။",
        "a_del_song_confirm": "⚠️ <b>{name}</b> ကို ဖျက်မည်လား?",
        "a_del_cat_confirm": "⚠️ <b>{name}</b> အမျိုးအစား ကို ဖျက်မည်လား?\n\nထဲမှ Album <b>{n}</b> ခုနှင့် ၎င်းတို့၏ သီချင်းများ အားလုံး ပါ ဖျက်ပါမည်။",
        "a_del_album_done": "🗑 Album ဖျက်ပြီးပါပြီ!",
        "a_del_song_done": "🗑 သီချင်း ဖျက်ပြီးပါပြီ!",
        "a_del_cat_done": "🗑 အမျိုးအစား ဖျက်ပြီးပါပြီ!",
        "a_move_no_cat": "⚠️ အမျိုးအစား မရှိသေးပါ!",
        "a_move_pick": "📂 <b>ဤအယ်လ်ဘမ်ကို မည်သည့် အမျိုးအစားသို့ ရွှေ့မည်လဲ?</b>",
        "a_move_done": "✅ <b>{album}</b>\n📂 <b>{cat}</b> အမျိုးအစားသို့ ရွှေ့ပြီးပါပြီ!",
        "a_done_all": "✅ <b>ဖျက်ပြီးပါပြီ!</b>\n\n{what} မကျန်တော့ပါ။",
        "a_what_albums": "Album",
        "a_what_songs": "သီချင်း",
        "a_what_cats": "အမျိုးအစား",
        "a_cat_added": "✅ <b>အမျိုးအစား ထည့်ပြီးပါပြီ!</b>",
        "a_cat_desc_prompt": "📝 <b>ဖော်ပြချက် ရိုက်ထည့်ပါ (မလိုရင် /skip):</b>",
        "a_skip_hint": "မလိုရင် /skip",

        # admin: upload flow
        "a_upload_choose_cat": "📀 <b>Album တင်မည့် အမျိုးအစား ရွေးပါ:</b>",
        "a_upload_first_cat": "⚠️ ဦးစွာ အမျိုးအစား (category) ထည့်ပါ!",
        "a_upload_started": (
            "🎼 <b>Album တင်ခြင်း စတင်နေသည်</b>\n\n"
            "1️⃣ ကာဗာပုံ (optional): photo ပို့ပါ — caption ထဲ Album နာမည် ရေးနိုင်သည်\n"
            "   (ပုံမလိုရင် ဤအဆင့် ကျော်နိုင်သည်)\n"
            "2️⃣ သီချင်းများ: audio file / forward ပို့ပါ — အားလုံး ပို့ပြီးရင် "
            "\"✅ ပြီးပါပြီ\" နှိပ်ပါ\n\n"
            "💡 Artist grouping: သီချင်း audio ရဲ့ performer (or caption "
            "'Song | Artist') နဲ့ အနုပညာရှင်ကို ခွဲသိမ်းပါမည် — name တူရင် "
            "အနုပညာရှင် တစ်ဦးအောက် ပြန်စုပါမည်"
        ),
        "a_upload_cover_received": "🖼 <b>ကာဗာပုံ ရရှိပြီ!</b>",
        "a_upload_album_name_set": "📀 Album နာမည်: <b>{name}</b>",
        "a_upload_send_songs": "အခု သီချင်းများ ပို့ပါ 👇",
        "a_upload_song_line": "📥 <b>သီချင်း ({n})</b> ✅\n\n🎵 <b>{title}</b>{artist_line}\n📀 {album}\n\nထပ်ပို့ပါ — ပြီးရင် \"✅ ပြီးပါပြီ\" ခလုတ် သို့မဟုတ် /done 👇",
        "a_upload_artist_line": "\n🎤 {artist}",
        "a_upload_no_artist": "\n⚠️ အဆိုတော် နာမည် မပါပါ — caption 'Song | Artist' ဖြင့် ပို့နိုင်သည်",
        "a_upload_audio_only": "⚠️ <b>အသံဖိုင် သာ ပို့နိုင်ပါသည်။</b>",
        "a_upload_unreadable": "⚠️ <b>ဤဖိုင်ကို မဖတ်နိုင်ပါ — နောက်တစ်ခု စမ်းပါ။</b>",
        "a_upload_wrong_type": "⚠️ အသံဖိုင်ကို forward/ပို့ပါ၊ သို့မဟုတ် photo ပို့ပါ — ပြီးရင် \"✅ ပြီးပါပြီ\" ခလုတ် သို့မဟုတ် /done ပါ။",
        "a_upload_set_album": "📀 <b>{name}</b>\n\nအခု သီချင်းများ ပို့ပါ 👇",
        "a_upload_finish_btn": "✅ ပြီးပါပြီ",
        "a_upload_finish_btn_only": "✅ ပြီးပါပြီ",
        "a_upload_cancel_btn": "❌ ရပ်လိုက်မည်",
        "a_upload_cancelled": "❌ <b>တင်ခြင်း ရပ်လိုက်ပါပြီ</b>",
        "a_upload_finished": (
            "✅ <b>ထည့်ပြီးပါပြီ!</b>\n\n"
            "🎵 သီချင်း: <b>{songs}</b> ပုဒ်\n"
            "🎤 အနုပညာရှင်: <b>{artists}</b>\n"
            "📀 Album: <b>{albums}</b>\n\n"
            "<b>သိမ်းထားသော Album များ:</b>\n{listing}"
        ),
        "a_upload_saved_prompt": "\"✅ ပြီးပါပြီ\" ခလုတ် (သို့) /done နှိပ်ပါ",
        "a_upload_save_failed": "⚠️ <b>ဤသီချင်းကို သိမ်း၍မရပါ</b>\n\nအမှား: <code>{err}</code>\n\nပြန်လည် ပို့ကြည့်ပါ သို့မဟုတ် /upload ဖြင့် ထပ်စမ်းပါ။",

        # admin: add album (legacy flow)
        "a_album_name_prompt": "📀 <b>အယ်လ်ဘမ် အမည် ရိုက်ထည့်ပါ:</b>",
        "a_album_artist_prompt": "🎤 <b>အနုပညာရှင် အမည် ရိုက်ထည့်ပါ (မလိုရင် /skip):</b>",
        "a_album_cover_prompt": "🖼 <b>အယ်လ်ဘမ် ကာဗာပုံ ပို့ပါ (မလိုရင် /skip):</b>",
        "a_album_cover_wrong": "🖼 <b>ကာဗာအတွက် ပုံ ပို့ပါ သို့မဟုတ် /skip နှိပ်ပါ:</b>",
        "a_album_added": "✅ <b>အယ်လ်ဘမ် ထည့်ပြီးပါပြီ!</b>\n\n📀 <b>{name}</b>\n{artist_line}\nအခု သီချင်းများ ထည့်နိုင်ပါပြီ 👇",
        "a_album_added_artist": "🎤 {artist}\n",

        # admin: add songs to existing album
        "a_batch_begin": (
            "🎵 <b>သီချင်းများ ထည့်မည်</b>\n\n📀 <b>{album}</b>\n\n"
            "1️⃣ ချန်နယ် (သို့) အခြားနေရာမှ အသံဖိုင်များကို forward/ပို့ပါ — "
            "တစ်ခါတည်း အများကြီး ပို့လို့ရပါသည်\n"
            "2️⃣ အားလုံး ပို့ပြီးရင် \"✅ ပြီးပါပြီ\" ခလုတ် (သို့မဟုတ် /done) နှိပ်ပါ\n\n"
            "💡 သီချင်းတစ်ပုဒ်ချင်းစီ နာမည် သတ်မှတ်ချင်ရင် ဖိုင်မပို့ခင် "
            "နာမည် ဦးစွာ ရိုက်ထည့်နိုင်ပါသည် (မထည့်ရင် ဖိုင်မှ metadata အတိုင်း ယူပါမည်)"
        ),
        "a_batch_song_added": "📥 <b>သီချင်း ({n})</b> ✅\n\n🎵 <b>{title}</b>\n📀 {album} ထဲ ထည့်ပြီးပါပြီ။\nထပ်ပို့ပါ — အားလုံးပြီးရင် \"✅ ပြီးပါပြီ\" ခလုတ် သို့မဟုတ် /done နှိပ်ပါ 👇",
        "a_batch_title_set": "🎵 နာမည် သတ်မှတ်ပြီ — <b>{title}</b>\nအခု သီချင်းဖိုင် ပို့ပါ 👇",
        "a_batch_audio_only": "⚠️ <b>အသံဖိုင် (.mp3) ပို့ပါ</b> သို့မဟုတ် \"✅ ပြီးပါပြီ\" ခလုတ် (သို့မဟုတ် /done) နှိပ်ပါ။",
        "a_batch_none": "⚠️ <b>သီချင်း မထည့်ရသေးပါ!</b>\n\nအသံဖိုင်များ forward ပို့ပြီးမှ \"✅ ပြီးပါပြီ\" ခလုတ် နှိပ်ပါ။",
        "a_batch_done": "✅ <b>ပြီးပါပြီ!</b>\n\n📀 {album}\n🎵 ထည့်ပြီး သီချင်း: <b>{n}</b> ပုဒ်\n\n🎧 User များ အခု album ထဲမှ နားဆင် / ဒေါင်းလုဒ်လို့ ရပါပြီ!",
        "a_batch_cancelled": "❌ <b>ထည့်ခြင်း ရပ်လိုက်ပါပြီ</b>\n\n(ထည့်ပြီးသား သီချင်းများမှာ သိမ်းထားပြီးသား ဖြစ်ပါသည်)",
        "a_btn_add_songs_here": "🎵 ဤအယ်လ်ဘမ်ထဲ သီချင်းထည့်မည်",
        "a_btn_view_album": "📀 အယ်လ်ဘမ် ကြည့်ရန်",
        "a_btn_next_song": "🎵 နောက်တစ်ပုဒ် ထည့်မည်",
        "a_btn_finish": "✅ ပြီးပါပြီ",
        "a_btn_delete_batch": "❌ ဖျက်မည်",
    },
    "en": {
        # -------- common --------
        "back": "🔙 Back",
        "close_btn": "❌ Close",
        "closed": "❌ Closed",
        "admin_menu_btn": "🏠 Admin Menu",
        "not_admin": "❌ You are not an admin!",
        "not_admin_short": "❌ You are not an admin.",
        "error_generic": "⚠️ Something went wrong.",
        "song_not_found": "❌ Song not found!",
        "sent_ok": "🎵 Sent!",
        "deleted_ok": "🗑 Deleted!",
        "cancel_label": "❌ Stop",
        "confirm_yes": "✅ Delete",
        "confirm_no": "❌ Cancel",

        # -------- welcome --------
        "welcome": (
            "🎵 Welcome to <b>Music Bot</b>! 🌟\n\n"
            "Easily search, listen to and download your favourite songs here.\n\n"
            "⬇️ Use the buttons below to get started:"
        ),
        "help": (
            "🆘 <b>Help</b>\n\n"
            "🎵 <b>How to use:</b>\n"
            "• 📀 Categories — browse albums by category\n"
            "• 🎤 Artists — pick an artist to see all their albums\n"
            "• Tap a song and the bot sends it to the chat\n"
            "• 🔍 Search — type an artist or song name\n"
            "• 💬 In any chat type <code>@{bot} song name</code> to search\n"
            "• ⚙️ Settings — switch language (Myanmar/English)\n\n"
            "<b>Commands:</b>\n"
            "/start - Start\n"
            "/help - Help\n"
            "/menu - Main menu\n"
            "/search &lt;name&gt; - Search artist / song\n"
            "/admin - (admin) Manage\n"
            "/upload - (admin) Upload album + songs"
        ),
        "admin_panel": (
            "⚙️ <b>Admin Menu</b>\n\n"
            "You can perform the following actions:\n\n"
            "➕ Add category / album / song\n"
            "🗑 Delete\n"
            "📊 View statistics"
        ),

        # -------- main menu --------
        "m_cats": "📀 Categories",
        "m_artists": "🎤 Artists",
        "m_songs": "🎵 Songs",
        "m_popular": "🔥 Popular",
        "m_new": "🆕 New",
        "m_search": "🔍 Search",
        "m_admin": "⚙️ Admin Menu",
        "m_settings": "⚙️ Settings",

        # -------- settings --------
        "settings_title": "⚙️ <b>Settings</b>\n\n🌐 Choose a language:",
        "lang_label": "🌐 Language",
        "lang_set": "✅ Language changed to <b>{name}</b>",

        # -------- categories --------
        "cats_header": "📂 <b>Choose a category:</b>",
        "cats_empty": "📂 No categories yet.",
        "cat_actions_hint": "Choose an action:",
        "btn_cat_albums": "📀 Albums",
        "btn_add_album": "➕ Add Album",
        "btn_del_cat": "🗑 Delete Category",

        # -------- albums --------
        "albums_header": "📀 <b>Albums:</b>",
        "albums_empty": "📂 No albums yet!",
        "album_dl_label": "📥 Downloads: {n}",
        "album_actions_hint": "Choose an action:",
        "btn_album_songs": "🎵 Songs",
        "btn_album_download_all": "📥 Download all",
        "btn_add_song": "➕ Add Song",
        "btn_move_cat": "📂 Change Category",
        "btn_del_album": "🗑 Delete Album",

        # -------- songs --------
        "songs_header": "🎵 <b>Songs ({n}):</b>",
        "songs_empty": "🎵 No songs yet!",
        "dl_album_header": "📀 <b>Songs in album ({n})</b>\n\nPick a song to receive:",
        "dl_count_short": "(DL: {n})",

        # -------- artists --------
        "artists_header": "🎤 <b>Artists ({n}):</b>\n\nPick an artist to see their albums:",
        "artists_empty": "🎤 No artists yet!",
        "artist_header": "🎤 <b>{name}</b>\n📀 Albums: {n}\n\nPick an album:",
        "artist_albums_empty": "📀 No albums for this artist yet!",

        # -------- search --------
        "search_prompt": "🔍 <b>Type an artist or song name to search:</b>",
        "search_need_query": "❌ Please enter a name to search.",
        "search_not_found": "😔 Nothing found for '{q}'.\nTry a different name.",
        "search_results_header": "🔍 <b>Results for '{q}' ({n}):</b>",
        "search_artists_header": "🔍 <b>Artists for '{q}' ({n}):</b>",
        "btn_next_page": "Next ▶️",
        "btn_prev_page": "◀️ Prev",
        "page_indicator": "📄 Page {page}/{pages}",
        "search_inline_empty": "Type a name to search",

        # -------- popular / new --------
        "popular_header": "🔥 <b>Popular songs (Top 10):</b>",
        "popular_empty": "🔥 No popular songs yet!",
        "new_header": "🆕 <b>Recently added songs (last 10):</b>",
        "new_empty": "🆕 No songs added yet!",

        # -------- stats --------
        "stats_header": "📊 <b>Statistics:</b>",
        "stats_songs": "🎵 Songs: <b>{n}</b>",
        "stats_albums": "📀 Albums: <b>{n}</b>",
        "stats_users": "👥 Users: <b>{n}</b>",
        "version_info": (
            "⚙️ <b>Bot Build</b>\n\n"
            "🆕 Version: <code>{ver}</code>\n"
            "🎵 Songs: {songs}\n"
            "📀 Albums: {albums}\n"
            "👥 Users: {users}"
        ),

        # -------- channel --------
        "ch_saved": "✅ <b>New song added!</b>\n\n🎧 {title}\n🎤 {artist}\n📀 {album}\n\n🤖 Open the bot chat to get it",
        "ch_duplicate": "ℹ️ This song is already saved.",
        "announce_new": "🆕 <b>New songs added</b>\n\n🎵 {n} track(s) — 🎤 {artists}\n🎧 Now available in the bot",

        # -------- admin: general --------
        "a_nothing_pending": "⚠️ No songs sent yet!",
        "a_no_flow": "ℹ️ No active upload flow.",
        "a_bf_start": "🌐 Translating existing songs (English ⇄ Myanmar)... please wait.",
        "a_bf_progress": "🌐 Translating... ({n} done)",
        "a_bf_done": "✅ Translation backfill complete — {n} songs updated.",
        "a_bf_none": "ℹ️ Nothing to translate (all songs already done).",
        "a_bf_failed": "❌ Translation failed: {err}",
        "a_imp_no_channel": "⚠️ CHANNEL_ID is not configured.",
        "a_imp_no_creds": "⚠️ TG_API_ID / TG_API_HASH are not set.\nGet api_id/api_hash from my.telegram.org and add them in Render Environment.",
        "a_imp_start": "📥 Importing songs from the channel into the bot... please wait.",
        "a_imp_progress": "📥 Importing... ({scanned}/{total} | new {added} | skipped {skipped})",
        "a_imp_done": "✅ Import finished.\nScanned: {scanned}\nAdded: {added}\nReplaced: {replaced}\nSkipped (already saved): {skipped}",
        "a_imp_failed": "❌ Import failed: {err}",
        "a_imp_peer_hint": "💡 A bot cannot read a private channel's history from its numeric id. Set CHANNEL_ID to the channel's @username and retry (the channel must be public).",
        "a_imp_need_post": "📮 The bot hasn't seen this private channel yet, so it can't resolve its id. <b>Post any message in the channel</b> — the bot will wait up to 90 seconds.",
        "a_imp_need_forward": "📮 To resolve a private channel's id, <b>forward any single message from that channel to me</b>. Then run /importchannel again.",
        "a_imp_forward_ok": "✅ Forward received. Run /importchannel again to start import.",
        "a_add_cat_prompt": "➕ <b>Type the category name:</b>",
        "a_add_cat_empty": "⚠️ Add a category first!",
        "a_choose_album_cat": "📀 <b>Choose a category for the album:</b>",
        "a_add_song_first_cat": "⚠️ Add a category first!",
        "a_choose_song_cat": "🎵 <b>Choose a category for the song:</b>",
        "a_no_album_in_cat": "⚠️ No album in this category!",
        "a_choose_song_album": "📀 <b>Choose the album for the song:</b>",
        "a_delete_choose": "🗑 <b>What do you want to delete?</b>",
        "a_del_btn_song": "🗑 Delete Song",
        "a_del_btn_album": "🗑 Delete Album",
        "a_del_btn_cat": "🗑 Delete Category",
        "a_del_no_cat": "⚠️ No category to delete!",
        "a_del_choose_cat": "🗑 <b>Choose a category to delete:</b>",
        "a_del_no_album": "⚠️ No album to delete!",
        "a_del_choose_album": "🗑 <b>Choose an album to delete:</b>\n\n(Deleting an album also deletes its songs)",
        "a_del_no_song": "⚠️ No song to delete!",
        "a_del_choose_song": "🗑 <b>Choose a song to delete:</b>",
        "a_del_album_confirm": "⚠️ Delete <b>{name}</b>?\n\nIts <b>{n}</b> song(s) will be deleted too.",
        "a_del_song_confirm": "⚠️ Delete <b>{name}</b>?",
        "a_del_cat_confirm": "⚠️ Delete category <b>{name}</b>?\n\nIts <b>{n}</b> album(s) and all their songs will be deleted too.",
        "a_del_album_done": "🗑 Album deleted!",
        "a_del_song_done": "🗑 Song deleted!",
        "a_del_cat_done": "🗑 Category deleted!",
        "a_move_no_cat": "⚠️ No categories yet!",
        "a_move_pick": "📂 <b>Move this album to which category?</b>",
        "a_move_done": "✅ Moved <b>{album}</b> to <b>{cat}</b>",
        "a_done_all": "✅ <b>Deleted!</b>\n\nNo {what} left.",
        "a_what_albums": "albums",
        "a_what_songs": "songs",
        "a_what_cats": "categories",
        "a_cat_added": "✅ <b>Category added!</b>",
        "a_cat_desc_prompt": "📝 <b>Type a description (or /skip):</b>",
        "a_skip_hint": "/skip to skip",

        # admin: upload flow
        "a_upload_choose_cat": "📀 <b>Choose a category to upload the album into:</b>",
        "a_upload_first_cat": "⚠️ Add a category (category) first!",
        "a_upload_started": (
            "🎼 <b>Album upload started</b>\n\n"
            "1️⃣ Cover image (optional): send a photo — you can put the album name in its caption\n"
            "   (skip this step if you don't want a cover)\n"
            "2️⃣ Songs: send/forward audio files — when done press \"✅ Done\"\n\n"
            "💡 Artist grouping: songs are grouped by the audio's performer "
            "(or caption 'Song | Artist') — same name groups under one artist"
        ),
        "a_upload_cover_received": "🖼 <b>Cover received!</b>",
        "a_upload_album_name_set": "📀 Album name: <b>{name}</b>",
        "a_upload_send_songs": "Now send the songs 👇",
        "a_upload_song_line": "📥 <b>Song ({n})</b> ✅\n\n🎵 <b>{title}</b>{artist_line}\n📀 {album}\n\nSend more — when done press \"✅ Done\" or /done 👇",
        "a_upload_artist_line": "\n🎤 {artist}",
        "a_upload_no_artist": "\n⚠️ No artist — send with caption 'Song | Artist'",
        "a_upload_audio_only": "⚠️ <b>Only audio files are allowed.</b>",
        "a_upload_unreadable": "⚠️ <b>Could not read this file — try another.</b>",
        "a_upload_wrong_type": "⚠️ Forward/send an audio file, or send a photo — then press \"✅ Done\" or /done.",
        "a_upload_set_album": "📀 <b>{name}</b>\n\nNow send the songs 👇",
        "a_upload_finish_btn": "✅ Done",
        "a_upload_finish_btn_only": "✅ Done",
        "a_upload_cancel_btn": "❌ Stop",
        "a_upload_cancelled": "❌ <b>Upload cancelled</b>",
        "a_upload_finished": (
            "✅ <b>Done!</b>\n\n"
            "🎵 Songs: <b>{songs}</b>\n"
            "🎤 Artists: <b>{artists}</b>\n"
            "📀 Albums: <b>{albums}</b>\n\n"
            "<b>Saved albums:</b>\n{listing}"
        ),
        "a_upload_saved_prompt": "Press \"✅ Done\" or /done",
        "a_upload_save_failed": "⚠️ <b>Could not save this song</b>\n\nError: <code>{err}</code>\n\nTry sending again or use /upload.",

        # admin: add album (legacy flow)
        "a_album_name_prompt": "📀 <b>Type the album name:</b>",
        "a_album_artist_prompt": "🎤 <b>Type the artist name (or /skip):</b>",
        "a_album_cover_prompt": "🖼 <b>Send the album cover (or /skip):</b>",
        "a_album_cover_wrong": "🖼 <b>Send an image for the cover, or /skip:</b>",
        "a_album_added": "✅ <b>Album added!</b>\n\n📀 <b>{name}</b>\n{artist_line}\nYou can now add songs 👇",
        "a_album_added_artist": "🎤 {artist}\n",

        # admin: add songs to existing album
        "a_batch_begin": (
            "🎵 <b>Add songs</b>\n\n📀 <b>{album}</b>\n\n"
            "1️⃣ Forward/send audio files from a channel or elsewhere — "
            "you can send many at once\n"
            "2️⃣ When done press \"✅ Done\" (or /done)\n\n"
            "💡 To set a per-song title, type the name before sending the file "
            "(otherwise metadata is used)"
        ),
        "a_batch_song_added": "📥 <b>Song ({n})</b> ✅\n\n🎵 <b>{title}</b>\n📀 Added to {album}.\nSend more — when done press \"✅ Done\" or /done 👇",
        "a_batch_title_set": "🎵 Title set — <b>{title}</b>\nNow send the audio file 👇",
        "a_batch_audio_only": "⚠️ <b>Send an audio file (.mp3)</b> or press \"✅ Done\" (or /done).",
        "a_batch_none": "⚠️ <b>No songs added yet!</b>\n\nForward audio files first, then press \"✅ Done\".",
        "a_batch_done": "✅ <b>Done!</b>\n\n📀 {album}\n🎵 Added songs: <b>{n}</b>\n\n🎧 Users can now listen / download from this album!",
        "a_batch_cancelled": "❌ <b>Add cancelled</b>\n\n(Already-added songs are kept)",
        "a_btn_add_songs_here": "🎵 Add songs to this album",
        "a_btn_view_album": "📀 View album",
        "a_btn_next_song": "🎵 Add another song",
        "a_btn_finish": "✅ Done",
        "a_btn_delete_batch": "❌ Delete",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Translate *key* into *lang* (falls back to Burmese, then the key)."""
    lang = lang if lang in TRANSLATIONS else DEFAULT_LANG
    text = TRANSLATIONS[lang].get(key)
    if text is None:
        text = TRANSLATIONS[DEFAULT_LANG].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


async def get_lang(user_id) -> str:
    """Return the stored language for a user (defaults to Myanmar)."""
    if user_id in _LANG_CACHE:
        return _LANG_CACHE[user_id]
    lang = DEFAULT_LANG
    try:
        from database import db
        doc = await db.db.users.find_one({"_id": user_id}, {"lang": 1})
        if doc and doc.get("lang") in SUPPORTED:
            lang = doc["lang"]
    except Exception:
        pass
    _LANG_CACHE[user_id] = lang
    return lang


async def set_lang(user_id, lang) -> str:
    """Persist the user's language choice and update the cache."""
    if lang not in SUPPORTED:
        lang = DEFAULT_LANG
    _LANG_CACHE[user_id] = lang
    try:
        from database import db
        await db.db.users.update_one(
            {"_id": user_id}, {"$set": {"lang": lang}}, upsert=True
        )
    except Exception:
        pass
    return lang
