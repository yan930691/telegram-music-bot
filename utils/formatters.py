import datetime
import html
import re


def format_size(size_bytes):
    """Format file size in readable format."""
    if not size_bytes:
        return "N/A"
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_duration(seconds):
    """Format duration in readable format."""
    if not seconds:
        return "မရရှိပါ"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    return f"{m} မိနစ် {s} စက္ကန့်"


def clean_filename(name):
    """Clean filename to safe for filesystem + Telegram."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.replace(" ", "_")
    return name.strip("_")


def split_caption(caption):
    """Split a caption like 'Album | Song | Artist' or 'Album | Song'."""
    if not caption:
        return []
    return [p.strip() for p in caption.split("|")]


def escape_markdown(text):
    """Escape Telegram MarkdownV2 special characters."""
    special = "_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{ch}" if ch in special else ch for ch in text)


def get_welcome_text():
    return (
        "🎵 <b>ဂီတ Bot</b> မှ ကြိုဆိုပါတယ်! 🌟\n\n"
        "ဤ bot တွင် သင်နှစ်သက်သော သီချင်းများကို "
        "အလွယ်တကူ ရှာဖွေ နားထောင် ဒေါင်းလုဒ် လုပ်နိုင်ပါသည်။\n\n"
        "⬇️ အောက်ပါ ခလုတ်များမှတစ်ဆင့် စတင်အသုံးပြုနိုင်ပါသည်:"
    )


def get_help_text():
    return (
        "🆘 <b>အကူအညီ</b>\n\n"
        "🎵 <b>Bot အသုံးပြုနည်း:</b>\n"
        "• 📀 သီချင်းအမျိုးအစားများ — အမျိုးအစားအလိုက် Album ရွေးနိုင်သည်\n"
        "• 🎤 အနုပညာရှင်များ — အဆိုတော်ရွေးပါက ၎င်း၏ Album အားလုံး ပြပါသည်\n"
        "• သီချင်းကို နှိပ်လိုက်ရင် bot က chat ထဲ ပို့ပေးပါသည်\n"
        "• 🔍 ရှာဖွေ ခလုတ်ဖြင့် အဆိုတော် / သီချင်းအမည် ရိုက်ပြီး ရှာဖွေနိုင်သည်\n\n"
        "<b>လုပ်ဆောင်ချက် (Command) များ:</b>\n"
        "/start - စတင်ခြင်း\n"
        "/help - အကူအညီ\n"
        "/menu - အဓိက မီနူး\n"
        "/search &lt;အမည်&gt; - အဆိုတော် / သီချင်း ရှာဖွေရန်\n"
        "/admin - (အက်ဒမင် အတွက်) စီမံခန့်ခွဲရန်\n"
        "/upload - (အက်ဒမင် အတွက်) Album + သီချင်း သွင်းရန်\n\n"
        "🔊 <b>Voice Chat (VC) ဖွင့်ခြင်း (group အတွင်း):</b>\n"
        "/play &lt;သီချင်းအမည် / YouTube link&gt; - VC ထဲ သီချင်းဖွင့်ရန်\n"
        "/vplay &lt;...&gt; - ဗီဒီယို ဖွင့်ရန်\n"
        "/pause - ရပ်ရန် | /resume - ပြန်ဖွင့်ရန်\n"
        "/skip - ကျော်ရန် | /stop - ရပ်ရှင်းရန်\n"
        "/queue - တန်းစီစာရင်း | /seek &lt;စက္ကန့်&gt; - ရှေ့ကျော်ရန်"
    )


def get_admin_panel_text():
    return (
        "⚙️ <b>အက်ဒမင် မီနူး</b>\n\n"
        "အောက်ပါ လုပ်ဆောင်ချက်များ ပြုလုပ်နိုင်ပါသည်:\n\n"
        "➕ အမျိုးအစား / အယ်လ်ဘမ် / သီချင်း ထည့်ခြင်း\n"
        "🗑 ဖျက်ခြင်း\n"
        "📊 စာရင်းဇယားကြည့်ခြင်း"
    )


# ===================== Voice Chat (VC) streaming messages =====================

def vc_now_playing(title, duration="00:00", requester=""):
    return (
        "▶️ <b>ဖွင့်နေသည်</b>\n\n"
        f"🎵 <b>{html.escape(str(title))}</b>\n"
        f"⏱ {duration}\n"
        f"👤 {html.escape(str(requester or '-'))}"
    )


def vc_replaying():
    return "🔁 လက်ရှိသီချင်းကို ပြန်ဖွင့်နေသည်..."


def vc_queue_empty():
    return "⏹ တန်းစီစာရင်း ကုန်သွားပါပြီ။"


def vc_stopped():
    return "⏹ ဖွင့်ခြင်းကို ရပ်လိုက်ပါပြီ။"


def vc_added_queue(position, title, requester=""):
    return (
        f"➕ <b>တန်းစီစာရင်းထဲ ထည့်လိုက်ပါပြီ (#{position})</b>\n\n"
        f"🎵 {html.escape(str(title))}\n"
        f"👤 {html.escape(str(requester or '-'))}"
    )


def vc_searching():
    return "🔍 ရှာဖွေနေသည်..."


def vc_downloading():
    return "⬇️ ဒေါင်းလုဒ်လုပ်နေသည်..."


def vc_no_active_call():
    return (
        "📵 <b>Group Voice Chat မဖွင့်ရသေးပါ။</b>\n\n"
        "ကျေးဇူးပြု၍ group ထဲ Voice Chat စတင်ပြီး ထပ်စမ်းပါ။"
    )


def vc_not_playing():
    return "⚠️ လက်ရှိ ဖွင့်နေတဲ့ သီချင်း မရှိပါ။"


def vc_paused():
    return "⏸ ရပ်ထားလိုက်ပါပြီ။"


def vc_resumed():
    return "▶️ ပြန်ဖွင့်လိုက်ပါပြီ။"


def vc_skipped():
    return "⏭ ကျော်လိုက်ပါပြီ။"


def vc_assistant_missing():
    return (
        "🚫 <b>Assistant အကောင့်ကို group ထဲ ထည့်ထားဖို့ လိုပါသည်။</b>\n\n"
        "VC ဖွင့်တဲ့အကောင့် (SESSION ဖန်တီးထားတဲ့ အကောင့်) ကို "
        "ဒီ group ထဲ member အဖြစ် ထည့်ပေးပါ။"
    )


def vc_need_group():
    return "❌ VC ဖွင့်နိုင်ရန် group / supergroup ထဲမှာ အသုံးပြုပါ။"


def vc_error(msg=""):
    extra = f"\n\n<code>{html.escape(str(msg))}</code>" if msg else ""
    return "⚠️ တစ်ခုခု မှားသွားသည်။ ထပ်စမ်းကြည့်ပါ။" + extra


def vc_queue_header():
    return "🎶 <b>တန်းစီစာရင်း</b>"


def vc_queue_item(n, title, duration="00:00", requester=""):
    return (
        f"<b>{n}.</b> {html.escape(str(title))} — {duration}"
        f"  <i>({html.escape(str(requester or '-'))})</i>"
    )
