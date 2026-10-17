import re

from utils.i18n import t as _t, DEFAULT_LANG


def format_size(size_bytes, lang=DEFAULT_LANG):
    """Format file size in readable format."""
    if not size_bytes:
        return "N/A"
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_duration(seconds, lang=DEFAULT_LANG):
    """Format duration in readable format."""
    if not seconds:
        return "—" if lang != "my" else "မရရှိပါ"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    if lang == "my":
        return f"{m} မိနစ် {s} စက္ကန့်"
    return f"{m}m {s}s"


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


def get_welcome_text(lang=DEFAULT_LANG):
    return _t("welcome", lang)


def get_help_text(lang=DEFAULT_LANG, bot_username="this_bot"):
    return _t("help", lang, bot=bot_username)


def get_admin_panel_text(lang=DEFAULT_LANG):
    return _t("admin_panel", lang)
