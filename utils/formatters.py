import datetime
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
        "• မီနူးမှတစ်ဆင့် အမျိုးအစားနှင့် အယ်လ်ဘမ်များ ရွေးချယ်နိုင်သည်\n"
        "• သီချင်းကို နှိပ်လိုက်ရင် bot က chat ထဲ ပို့ပေးပါသည်\n"
        "• 🔍 ရှာဖွေ ခလုတ်ဖြင့် သီချင်းအမည်ရိုက်ပြီး ရှာဖွေနိုင်သည်\n\n"
        "<b>လုပ်ဆောင်ချက် (Command) များ:</b>\n"
        "/start - စတင်ခြင်း\n"
        "/help - အကူအညီ\n"
        "/menu - အဓိက မီနူး\n"
        "/search &lt;အမည်&gt; - သီချင်းရှာဖွေရန်\n"
        "/admin - (အက်ဒမင် အတွက်) စီမံခန့်ခွဲရန်"
    )


def get_admin_panel_text():
    return (
        "⚙️ <b>အက်ဒမင် မီနူး</b>\n\n"
        "အောက်ပါ လုပ်ဆောင်ချက်များ ပြုလုပ်နိုင်ပါသည်:\n\n"
        "➕ အမျိုးအစား / အယ်လ်ဘမ် / သီချင်း ထည့်ခြင်း\n"
        "🗑 ဖျက်ခြင်း\n"
        "📊 စာရင်းဇယားကြည့်ခြင်း"
    )
