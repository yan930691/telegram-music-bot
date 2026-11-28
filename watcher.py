"""NEW watcher only. Does not modify or replace any existing bot script.

Watches source channels at 09:00, 12:00, 17:00, 21:00 and 22:00 MMT (UTC+06:30), finds new
movie posts, and drives @UwinzawnyuntBot in its DM. It never posts to a
channel directly.

Rules implemented:
  - Only posts whose messages allow forwarding are sent (noforwards=False).
  - Clear photo (largest photo) is taken from the movie post itself. Video
    thumbnails are never used as the poster.
  - Series posts are skipped entirely (never forwarded to the bot).
  - Movie links are followed: t.me/c/<id>/<msg> OR "Tele » t.me/+invite",
    including the "ဇာတ်ကားကြည့်ရှု့ရန်လင့်" wording and homietv.com/movie slugs.
  - Every video/file in one movie item is forwarded in one bot flow.
  - Synopsis lookup: HomieTV /movies/pages/1..3 first, then TMDB fallback.
    TMDB English overview is translated to Burmese when a translation provider
    key is present; otherwise it is labelled as English (never claimed Burmese).
    Network failure is non-fatal.
  - Before posting, the movie is checked read-only against @wznmoviescollector.
  - After posting, time/title/link is written to Telegram Saved Messages.
  - Duplicates are skipped using local state AND the target-channel scan.

Run:
    set TG_API_ID=...
    set TG_API_HASH=...
    python movie_watch_forwarder.py                 # wait for next 9/12/17/21/22 slot
    python movie_watch_forwarder.py --now           # run once immediately
    python movie_watch_forwarder.py --dry-run       # decide only, send nothing
    python movie_watch_forwarder.py --script-test "movie title"

Optional env (all safe to set/change):
    WATCH_SOURCES=@kcsyoteshin001,@mwmainchannel007,@HomieTVkmovies9
    TARGET_BOT=@UwinzawnyuntBot
    TARGET_CHANNEL=@wznmoviescollector  # read-only duplicate check
    SAVED_CHAT=me                       # Telegram Saved Messages
    PUBLISHED_LINK_WAIT=45
    HOMIE_PAGES=1,2,3
    HOMIE_SEARCH_URL=https://www.homietv.com/movies/pages/{p}
    TMDB_API_KEY=...                   # free TMDB key, read from env only
    TRANSLATE_PROVIDER=auto            # auto|groq|openrouter|gemini|none
    GROQ_API_KEY=... / OPENROUTER_API_KEY=... / GEMINI_API_KEY=...
    DELAY=2.0
    TARGET_SCAN_LIMIT=1200
    STATE_FILE=movie_watch_state.json
"""

import argparse
import asyncio
import difflib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.sessions import StringSession
from telethon.tl.types import MessageService

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

MMT = timezone(timedelta(hours=6, minutes=30), name="MMT")
RUN_HOURS = (9, 12, 17, 21, 22)

SOURCES = [
    s.strip()
    for s in os.environ.get(
        "WATCH_SOURCES", "@kcsyoteshin001,@mwmainchannel007,@HomieTVkmovies9"
    ).split(",")
    if s.strip()
]
TARGET_BOT = os.environ.get("TARGET_BOT", "@UwinzawnyuntBot")
TARGET_CHANNEL = os.environ.get("TARGET_CHANNEL", "@wznmoviescollector")
SAVED_CHAT = os.environ.get("SAVED_CHAT", "me")
PUBLISHED_LINK_WAIT = float(os.environ.get("PUBLISHED_LINK_WAIT", "45"))
HOMIE_PAGES = [
    x.strip()
    for x in os.environ.get("HOMIE_PAGES", "1,2,3").split(",")
    if x.strip()
]
HOMIE_SEARCH_URL = os.environ.get(
    "HOMIE_SEARCH_URL", "https://www.homietv.com/movies/pages/{p}"
)
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "").strip()
TRANSLATE_PROVIDER = os.environ.get("TRANSLATE_PROVIDER", "auto").strip().lower()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free"
)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
DELAY = float(os.environ.get("DELAY", "2.0"))
TARGET_SCAN_LIMIT = int(os.environ.get("TARGET_SCAN_LIMIT", "1200"))
SCAN_LIMIT = int(os.environ.get("SCAN_LIMIT", "200"))
INVITE_SCAN_LIMIT = int(os.environ.get("INVITE_SCAN_LIMIT", "30"))
MAX_SEEN_KEYS = int(os.environ.get("MAX_SEEN_KEYS", "3000"))
STATE_FILE = os.environ.get(
    "STATE_FILE", os.path.join(HERE, "movie_watch_state.json")
)
LOG_FILE = os.path.join(HERE, "movie_watch_forwarder.log")


def log(msg: str) -> None:
    line = "[" + datetime.now(MMT).strftime("%Y-%m-%d %H:%M:%S MMT] ") + msg
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def safe_err(exc: BaseException) -> str:
    text = re.sub(r"https?://\S+", "[url]", str(exc))
    text = re.sub(r"[A-Za-z0-9_+/-]{40,}", "[redacted]", text)
    return type(exc).__name__ + ": " + text[:140]


def norm_title(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    first = lines[0]
    first = re.sub(r"^[^\w\u1000-\u109F]+", "", first, flags=re.UNICODE)
    if not first and len(lines) > 1:
        first = re.sub(r"^[^\w\u1000-\u109F]+", "", lines[1], flags=re.UNICODE)
    first = re.sub(r"https?://\S+", " ", first)
    first = re.sub(r"[^\w\u1000-\u109F]+", " ", first, flags=re.UNICODE)
    return re.sub(r"\s+", " ", first).strip().lower()


LINK_RE = re.compile(r"t\.me/c/(\d+)/(\d+)")
USER_LINK_RE = re.compile(r"t\.me/([A-Za-z0-9_]+)/(\d+)")
INVITE_RE = re.compile(r"https?://t\.me/\+([A-Za-z0-9_-]+)")
WEB_MOVIE_RE = re.compile(r"homietv\.com/movie/([A-Za-z0-9-]+)", re.I)

MOVIE_MARKERS = (
    "ဇာတ်ကားကြည့်ရှု့ရန်",
    "ဇာတ်ကားကြည့်ရှုရန်",
    "ဇာတ်ကားကြည့်ရန်",
    "ကြည့်ရှု့ရန်လင့်",
    "ကြည့်ရှုရန်လင့်",
    "ကြည့်ရန် လင့်",
    "movie link",
)

SERIES_PATTERNS = (
    r"\bseries\b",
    r"\bseason\s*\d+",
    r"\bs\d{1,2}\b",
    r"\bep(?:isode)?\.?\s*\d+",
    r"အပိုင်း\s*\d+",
    r"ပိုင်း\s*\d+",
    r"ဆီရီးဇ်",
    r"တွဲ",
)


def find_movie_link(caption: str):
    """Use the last t.me/c/<id>/<msg> link: that is the movie link in these posts."""
    found = LINK_RE.findall(caption or "")
    if not found:
        return None
    cid, mid = found[-1]
    return int("-100" + cid), int(mid)


def telegram_link(entity, msg_id: int) -> str:
    username = getattr(entity, "username", "") if entity else ""
    if username:
        return f"https://t.me/{username}/{msg_id}"
    raw = abs(int(getattr(entity, "id", 0) or 0))
    text = str(raw)
    if text.startswith("100") and len(text) > 3:
        return f"https://t.me/c/{text[3:]}/{msg_id}"
    return f"https://t.me/c/{text}/{msg_id}"


def is_forwardable(msg) -> bool:
    if getattr(msg, "noforwards", False):
        return False
    chat = getattr(msg, "chat", None)
    if chat is not None and getattr(chat, "noforwards", False):
        return False
    return True


def movie_messages(messages):
    out = []
    for m in messages:
        if isinstance(m, MessageService):
            continue
        video = getattr(m, "video", None)
        doc = getattr(m, "document", None)
        mime = str(getattr(doc, "mime", "") or "")
        if video or (doc and mime.startswith("video/")):
            out.append(m)
    return out


def photo_score(msg) -> int:
    photo = getattr(msg, "photo", None)
    if photo is None:
        return 0
    best = 0
    for size in getattr(photo, "sizes", []) or []:
        area = int(getattr(size, "w", 0) or 0) * int(getattr(size, "h", 0) or 0)
        best = max(best, area, int(getattr(size, "size", 0) or 0))
    return best


def best_photo(messages):
    photos = [m for m in messages if getattr(m, "photo", None) is not None]
    if not photos:
        return None
    return max(photos, key=photo_score)


def file_sig(msg) -> str:
    for attr in ("video", "document", "photo"):
        media = getattr(msg, attr, None)
        uid = getattr(media, "file_unique_id", "") if media else ""
        if uid:
            return str(uid)
    return ""


def has_movie_marker(caption: str) -> bool:
    low = (caption or "").lower()
    return any(marker in low for marker in MOVIE_MARKERS)


def is_series(caption: str, title: str = "") -> bool:
    text = ((caption or "") + " " + (title or "")).lower()
    return any(re.search(pattern, text) for pattern in SERIES_PATTERNS)


def find_invite_link(caption: str):
    match = INVITE_RE.search(caption or "")
    if not match:
        return None
    return "https://t.me/+" + match.group(1), match.group(1)


def slug_title(slug: str) -> str:
    text = re.sub(r"[-_]+", " ", slug or "").strip()
    text = re.sub(r"\b[A-Za-z0-9]{6,8}$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def caption_title(caption: str) -> str:
    web = WEB_MOVIE_RE.search(caption or "")
    slug = slug_title(web.group(1)) if web else ""
    lines = [ln.strip() for ln in (caption or "").splitlines() if ln.strip()]
    skip_prefixes = (
        "web »", "web»", "tele »", "tele»", "http://", "https://",
        "https://t.me/", "join", "အညွှန်း", "📝",
    )
    candidates = []
    for line in lines:
        low = line.lower()
        if low.startswith(skip_prefixes):
            continue
        if "t.me/" in low and len(line) < 140:
            continue
        candidates.append(line)
    if slug and (not candidates or "homietv.com" in candidates[0].lower()):
        return slug
    return candidates[0] if candidates else slug


async def collect_groups_newest(client, entity, limit: int):
    groups = []
    by_group = {}
    async for msg in client.iter_messages(entity, limit=limit):
        if isinstance(msg, MessageService):
            continue
        gid = getattr(msg, "grouped_id", None)
        if gid:
            if gid not in by_group:
                by_group[gid] = []
                groups.append(by_group[gid])
            by_group[gid].append(msg)
        else:
            groups.append([msg])
    return groups


async def find_movie_group_in_channel(client, entity, limit: int = 30):
    """Pick the newest forwardable group that has a movie + a clear photo."""
    groups = await collect_groups_newest(client, entity, limit)
    for group in groups:
        if not movie_messages(group):
            continue
        if best_photo(group) is None:
            continue
        if not all(is_forwardable(m) for m in group):
            continue
        return group
    return None


class State:
    def __init__(self, path):
        self.path = path
        self.data = {"last_ids": {}, "seen_keys": []}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except Exception:
            pass
        if not isinstance(self.data.get("last_ids"), dict):
            self.data["last_ids"] = {}
        if not isinstance(self.data.get("seen_keys"), list):
            self.data["seen_keys"] = []

    def last_id(self, key: str) -> int:
        try:
            return int(self.data["last_ids"].get(key, 0))
        except (TypeError, ValueError):
            return 0

    def set_last_id(self, key: str, msg_id: int) -> None:
        if msg_id > self.last_id(key):
            self.data["last_ids"][key] = int(msg_id)

    def seen(self, key: str) -> bool:
        return bool(key) and key in self.data["seen_keys"]

    def mark(self, keys) -> None:
        for key in keys:
            if key and key not in self.data["seen_keys"]:
                self.data["seen_keys"].append(key)
        self.data["seen_keys"] = self.data["seen_keys"][-MAX_SEEN_KEYS:]

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


class TextParser(HTMLParser):
    SKIP = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _fetch(url: str, timeout: int = 15) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 KOWIN-movie-watcher"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read(600_000)
    return raw.decode("utf-8", errors="replace")


def _fetch_json(url: str, timeout: int = 15):
    return json.loads(_fetch(url, timeout=timeout))


def _post_json(url: str, payload: dict, headers=None, timeout: int = 25):
    head = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 KOWIN-movie-watcher",
    }
    if headers:
        head.update(headers)
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=head,
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read(600_000).decode("utf-8"))


def _page_url(page: str, key: str) -> str:
    if "{p}" in HOMIE_SEARCH_URL:
        return HOMIE_SEARCH_URL.replace("{p}", str(page)).replace("{q}", quote_plus(key))
    return HOMIE_SEARCH_URL.replace("{q}", quote_plus(key))


def movie_query(title: str) -> str:
    lines = [ln.strip() for ln in (title or "").splitlines() if ln.strip()]
    q = lines[0] if lines else ""
    q = re.sub(r"https?://\S+", " ", q)
    q = re.sub(r"^[^\w\u1000-\u109F]+", "", q, flags=re.UNICODE)
    return re.sub(r"\s+", " ", q).strip()[:120]


def _synopsis_from_html(html: str, tokens) -> str:
    parser = TextParser()
    parser.feed(html)
    body = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    if len(body) < 60:
        return ""
    sentences = re.split(r"(?<=[.!?။])\s+", body)
    hits = []
    for sentence in sentences:
        if sum(1 for token in tokens if token in sentence.lower()) >= 1:
            hits.append(sentence.strip())
    picked = " ".join(hits[:6]) if hits else body
    return picked[:1500]


def homie_script(title: str):
    """Scan /movies/pages/1..3. Returns (text, source); empty text if not found."""
    key = norm_title(title)
    if not key:
        return "", ""
    tokens = [t for t in re.findall(r"\w+", key) if len(t) > 2]
    if not tokens:
        return "", ""

    candidates = []
    for page in HOMIE_PAGES:
        url = _page_url(page, key)
        try:
            html = _fetch(url)
        except Exception as exc:
            log("HomieTV page " + str(page) + " မရပါ: " + safe_err(exc))
            continue
        parser = LinkParser()
        parser.feed(html)
        for href, text in parser.links:
            full = urljoin(url, href or "")
            if "homietv.com" not in full:
                continue
            score = sum(1 for token in tokens if token in text.lower())
            if score:
                candidates.append((score, full))

        body = _synopsis_from_html(html, tokens)
        if body:
            return body, "HomieTV"

    if not candidates:
        return "", ""
    candidates.sort(reverse=True)
    try:
        html = _fetch(candidates[0][1])
    except Exception as exc:
        log("HomieTV ဇာတ်ကား page မရပါ: " + safe_err(exc))
        return "", ""
    body = _synopsis_from_html(html, tokens)
    return (body, "HomieTV") if body else ("", "")


def tmdb_overview(title: str) -> str:
    """Read-only TMDB search. Requires free TMDB_API_KEY from env, never bundled."""
    if not TMDB_API_KEY:
        return ""
    query = movie_query(title)
    if not query:
        return ""
    url = (
        "https://api.themoviedb.org/3/search/movie?api_key=" + quote_plus(TMDB_API_KEY)
        + "&language=en-US&page=1&query=" + quote_plus(query)
    )
    data = _fetch_json(url)
    scored = []
    for item in data.get("results") or []:
        overview = str(item.get("overview") or "").strip()
        if not overview:
            continue
        name = str(item.get("title") or item.get("original_title") or "").lower()
        score = difflib.SequenceMatcher(None, name, query.lower()).ratio()
        scored.append((score, overview))
    if not scored:
        return ""
    scored.sort(reverse=True)
    return scored[0][1][:1500]


TRANSLATE_PROMPT = (
    "Translate the following movie synopsis into natural, spoken Burmese suitable "
    "for a movie recap narration. Keep character and place names unchanged. "
    "Do not add explanations. Return only the Burmese translation."
)


def _translate_providers():
    if TRANSLATE_PROVIDER != "auto":
        return [TRANSLATE_PROVIDER] if TRANSLATE_PROVIDER != "none" else []
    order = []
    if os.environ.get("GROQ_API_KEY"):
        order.append("groq")
    if os.environ.get("OPENROUTER_API_KEY"):
        order.append("openrouter")
    if os.environ.get("GEMINI_API_KEY"):
        order.append("gemini")
    return order


def translate_to_burmese(text: str) -> str:
    if not text:
        return ""
    for provider in _translate_providers():
        try:
            if provider == "groq":
                data = _post_json(
                    "https://api.groq.com/openai/v1/chat/completions",
                    {
                        "model": GROQ_MODEL,
                        "messages": [
                            {"role": "system", "content": TRANSLATE_PROMPT},
                            {"role": "user", "content": text},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 900,
                    },
                    {"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]},
                )
                return str(data["choices"][0]["message"]["content"]).strip()
            if provider == "openrouter":
                data = _post_json(
                    "https://openrouter.ai/api/v1/chat/completions",
                    {
                        "model": OPENROUTER_MODEL,
                        "messages": [
                            {"role": "system", "content": TRANSLATE_PROMPT},
                            {"role": "user", "content": text},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 900,
                    },
                    {"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]},
                )
                return str(data["choices"][0]["message"]["content"]).strip()
            if provider == "gemini":
                data = _post_json(
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    + GEMINI_MODEL + ":generateContent?key=" + quote_plus(
                        os.environ["GEMINI_API_KEY"]
                    ),
                    {
                        "contents": [{
                            "parts": [{"text": TRANSLATE_PROMPT + "\n\n" + text}]
                        }],
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 900},
                    },
                )
                parts = data["candidates"][0]["content"]["parts"]
                return str("".join(p.get("text", "") for p in parts)).strip()
        except Exception as exc:
            log(provider + " ဘာသာပြန် မရပါ: " + safe_err(exc))
    return ""


def script_for_title(title: str):
    """HomieTV first, then TMDB + Burmese translation. Returns (text, source)."""
    script, source = homie_script(title)
    if script:
        return script, source

    overview = tmdb_overview(title)
    if not overview:
        return "", ""
    translated = translate_to_burmese(overview)
    if translated:
        return translated, "TMDB မြန်မာပြန်"
    return overview, "TMDB English (ဘာသာပြန် key မရှိ)"


async def group_messages(client, source, last_id: int):
    groups = []
    by_group = {}
    async for msg in client.iter_messages(
        source, min_id=last_id, reverse=True, limit=SCAN_LIMIT
    ):
        if isinstance(msg, MessageService):
            continue
        gid = getattr(msg, "grouped_id", None)
        if gid:
            if gid not in by_group:
                by_group[gid] = []
                groups.append(by_group[gid])
            by_group[gid].append(msg)
        else:
            groups.append([msg])
    return groups


async def build_item(client, label: str, source_entity, group):
    caption = next(
        (m.message for m in group if getattr(m, "message", "") and m.message.strip()),
        "",
    )
    display = caption_title(caption)
    title_key = norm_title(display) or norm_title(caption)
    if not title_key:
        return None, "no title"
    if is_series(caption, display):
        return None, "series — @UwinzawnyuntBot ဆီ မပို့ဘူး"

    first_line = caption.splitlines()[0] if caption.splitlines() else ""
    cleaned_caption = caption
    if display and norm_title(display) != norm_title(first_line):
        cleaned_caption = display + "\n" + caption

    post_entity = source_entity
    post_messages = group

    direct_videos = movie_messages(group)
    tme_link = find_movie_link(caption)
    invite = find_invite_link(caption)
    marker = has_movie_marker(caption)

    if tme_link and (
        "mwmain" in label.lower() or marker or not direct_videos
    ):
        channel_id, msg_id = tme_link
        try:
            post_entity = await client.get_entity(channel_id)
            fetched = await client.get_messages(channel_id, ids=[msg_id])
        except Exception as exc:
            return None, "link read failed: " + safe_err(exc)
        post_messages = [
            m for m in (fetched or []) if m and not isinstance(m, MessageService)
        ]
    elif invite and (marker or not direct_videos):
        invite_url, _ = invite
        try:
            post_entity = await client.get_entity(invite_url)
            found = await find_movie_group_in_channel(
                client, post_entity, INVITE_SCAN_LIMIT
            )
        except Exception as exc:
            return None, "invite read failed: " + safe_err(exc)
        if not found:
            return None, "invite ထဲမှာ ဇာတ်ကား မတွေ့ဘူး"
        post_messages = found
    elif "mwmain" in label.lower():
        return None, "no movie link"

    videos = movie_messages(post_messages)
    if not videos:
        return None, "no movie file"

    if not all(is_forwardable(m) for m in post_messages):
        return None, "forwarding disabled"

    poster = best_photo(post_messages)
    if poster is None:
        return None, "no clear photo"

    watch_id = max(m.id for m in group)
    post_id = max(m.id for m in post_messages)
    return {
        "label": label,
        "title": cleaned_caption.strip()[:4000],
        "title_key": title_key,
        "watch_link": telegram_link(source_entity, watch_id),
        "post_link": telegram_link(post_entity, post_id),
        "post_entity": post_entity,
        "poster_id": poster.id,
        "video_ids": [m.id for m in videos],
        "message_ids": [m.id for m in post_messages],
        "sigs": [s for m in post_messages if (s := file_sig(m))],
        "last_id": watch_id,
    }, ""


async def target_has_movie(client, title_key: str, sigs) -> bool:
    if not TARGET_CHANNEL:
        return False
    async for msg in client.iter_messages(TARGET_CHANNEL, limit=TARGET_SCAN_LIMIT):
        if norm_title(getattr(msg, "message", "")) == title_key:
            return True
        sig = file_sig(msg)
        if sig and sig in sigs:
            return True
    return False


async def send_text(client, bot, text: str) -> None:
    await client.send_message(bot, text)
    await asyncio.sleep(min(DELAY, 2.0))


async def forward_ids(client, entity, bot, ids) -> None:
    if not ids:
        return
    for _ in range(5):
        try:
            await client.forward_messages(bot, ids, from_peer=entity)
            await asyncio.sleep(max(1.0, DELAY * len(ids)))
            return
        except FloodWaitError as exc:
            wait = int(exc.seconds) + 3
            log(f"FloodWait {wait}s — စောင့်ပါမယ်")
            await asyncio.sleep(wait)
        except RPCError as exc:
            log("forward failed: " + safe_err(exc))
            return
    log("forward failed after retries")


async def wait_for_published_link(client, bot, since_id: int) -> str:
    """Best-effort: read the bot's DM reply for the published channel link."""
    deadline = asyncio.get_running_loop().time() + max(0.0, PUBLISHED_LINK_WAIT)
    while True:
        try:
            msgs = await client.get_messages(bot, limit=40)
        except Exception as exc:
            log("bot reply စစ်လို့မရပါ: " + safe_err(exc))
            return ""
        for msg in msgs or []:
            if not msg or getattr(msg, "out", False) or msg.id <= since_id:
                continue
            text = getattr(msg, "message", "") or ""
            for cid, mid in LINK_RE.findall(text):
                return f"https://t.me/c/{cid}/{mid}"
            for user, mid in USER_LINK_RE.findall(text):
                if user.lower() != "c":
                    return f"https://t.me/{user}/{mid}"
        if asyncio.get_running_loop().time() >= deadline:
            return ""
        await asyncio.sleep(3)


async def record_saved(client, item, published_link: str, when: datetime) -> None:
    title_line = next(
        (ln.strip() for ln in item["title"].splitlines() if ln.strip()),
        item["title_key"],
    )
    lines = [
        "📌 KOWIN Movie Watcher",
        "အချိန်: " + when.strftime("%Y-%m-%d %H:%M:%S MMT"),
        "ဇာတ်ကား: " + title_line[:160],
        "စောင့်ကြည့်ချန်နယ်: " + item["label"],
        "ရင်းမြစ်လင့်: " + item["watch_link"],
        "ဇာတ်ကားလင့်: " + item["post_link"],
        "ချန်နယ်လင့်: " + (published_link or "bot က လင့်မပြန်သေးဘူး"),
        "Bot: @" + str(TARGET_BOT).lstrip("@") + " (/newpost flow)",
    ]
    try:
        await client.send_message(SAVED_CHAT, "\n".join(lines))
        log("Saved Messages မှာ မှတ်ပြီး")
    except Exception as exc:
        log("Saved Messages မရေးနိုင်ပါ: " + safe_err(exc))


async def publish_item(client, bot, item):
    """Returns (ok, published_link)."""
    try:
        latest = await client.get_messages(bot, limit=1)
        since_id = latest[0].id if latest else 0

        await send_text(client, bot, "/start")
        await send_text(client, bot, "/newpost")

        caption = item["title"]
        try:
            script, source = script_for_title(caption)
        except Exception as exc:
            script, source = "", ""
            log("ဇာတ်ညွှန်း ရှာရင် error (အလုပ်မပိတ်ဘူး): " + safe_err(exc))
        if script:
            caption = caption + "\n\nဇာတ်ညွှန်း (" + source + ") — " + script
            log("ဇာတ်ညွှန်း ရပါတယ်: " + source)
        else:
            log("ဇာတ်ညွှန်း မရပါ — caption ပဲ ပို့မယ်")

        await send_text(client, bot, caption)
        await send_text(client, bot, "a")
        await forward_ids(client, item["post_entity"], bot, [item["poster_id"]])
        await forward_ids(client, item["post_entity"], bot, item["video_ids"])
        await send_text(client, bot, "a")

        published = await wait_for_published_link(client, bot, since_id)
        await record_saved(client, item, published, datetime.now(MMT))
        return True, published
    except Exception as exc:
        log("bot flow failed: " + safe_err(exc))
        return False, ""


async def scan_once(client, state: State, dry_run: bool) -> None:
    bot = await client.get_entity(TARGET_BOT)
    log("target bot: @" + str(getattr(bot, "username", TARGET_BOT)))

    try:
        await client.get_entity(TARGET_CHANNEL)
        log("duplicate check (read-only): @" + str(TARGET_CHANNEL).lstrip("@"))
    except Exception as exc:
        log("target channel စစ်လို့မရပါ — မတင်တော့ဘူး: " + safe_err(exc))
        return

    for raw in SOURCES:
        label = raw
        try:
            source = await client.get_entity(raw)
        except Exception as exc:
            log(f"{label}: source ဖွင့်လို့မရပါ — " + safe_err(exc))
            continue

        title = getattr(source, "title", label)
        key = str(getattr(source, "id", raw))
        last_id = state.last_id(key)
        log(f"== {title}: scan id > {last_id}")

        groups = await group_messages(client, source, last_id)
        if not groups:
            log("   အသစ်မရှိပါ")
            continue

        for group in groups:
            item, reason = await build_item(client, label, source, group)
            gid = max(m.id for m in group)
            keys = set()
            if item:
                keys.add(item["title_key"])
                keys.update(item["sigs"])

            if not item:
                log(f"   SKIP {gid}: {reason}")
                if not dry_run:
                    state.set_last_id(key, gid)
                    skipped_cap = next(
                        (m.message for m in group if getattr(m, "message", "")), ""
                    )
                    state.mark([norm_title(caption_title(skipped_cap))])
                continue

            if state.seen(item["title_key"]) or any(state.seen(s) for s in item["sigs"]):
                log(f"   SKIP {gid}: ဒီဇာတ်ကား ကိုယ်တိုင် ပြီးပြီး (local state)")
                if not dry_run:
                    state.set_last_id(key, gid)
                    state.mark(keys)
                continue

            try:
                exists = await target_has_movie(client, item["title_key"], item["sigs"])
            except Exception as exc:
                log(f"   SKIP {gid}: target စစ်ရင် error — " + safe_err(exc))
                continue
            if exists:
                log(f"   SKIP {gid}: ချန်နယ်မှာ တင်ထားပီးသား ဇာတ်ကား")
                if not dry_run:
                    state.set_last_id(key, gid)
                    state.mark(keys)
                continue

            log(f"   FOUND {gid}: {item['title_key'][:60]} | videos={len(item['video_ids'])}")
            if dry_run:
                log("   DRY-RUN — ဘာမှ မပို့ပါ")
                continue

            ok, published = await publish_item(client, bot, item)
            if ok:
                state.set_last_id(key, gid)
                state.mark(keys)
                state.save()
                log(f"   SENT {gid} | link=" + (published or "bot reply မရှိသေး"))
            else:
                log(f"   NOT SENT {gid} — last_id ကို မရွှေ့ဘူး၊ နောက်တစ်ခေါက် ပြန်လုပ်မယ်")

        if not dry_run:
            state.save()

    log(" scan finished")


def seconds_to_next_slot(now=None):
    now = now or datetime.now(MMT)
    slots = [now.replace(hour=h, minute=0, second=0, microsecond=0) for h in RUN_HOURS]
    future = [s for s in slots if s > now]
    if future:
        nxt = min(future)
    else:
        nxt = slots[0] + timedelta(days=1)
    return max(0, (nxt - now).total_seconds()), nxt


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true", help="run one scan immediately")
    ap.add_argument("--dry-run", action="store_true", help="decide only, send nothing")
    ap.add_argument(
        "--script-test", "--homie-test", dest="script_test", metavar="TITLE",
        help="test HomieTV then TMDB fallback",
    )
    args = ap.parse_args()

    if args.script_test:
        try:
            script, source = script_for_title(args.script_test)
            print("SCRIPT_RESULT:", source + " | " + (script[:300] if script else "NOT_FOUND"))
        except Exception as exc:
            print("SCRIPT_RESULT: ERROR " + safe_err(exc))
        return

    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        raise SystemExit("TG_API_ID / TG_API_HASH ကို environment မှာ ထည့်ပါ (values မပြပါဘူး)")

    session_file = os.environ.get("TG_SESSION_FILE", os.path.join(HERE, "session.txt"))
    try:
        with open(session_file, "r", encoding="utf-8") as fh:
            session = fh.read().strip()
    except Exception:
        raise SystemExit("session.txt ဖတ်လို့မရပါ။ TG_SESSION_FILE ညွှန်းပါ။")

    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    state = State(STATE_FILE)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise SystemExit("Session က authorize မဖြစ်တော့ဘူး။ အသစ်ထုတ်ပါ။")

    log("watcher started")
    try:
        if args.now:
            await scan_once(client, state, args.dry_run)
        else:
            while True:
                wait, when = seconds_to_next_slot()
                log(f"နောက်စစ်မည့်အချိန်: {when.strftime('%Y-%m-%d %H:%M MMT')} ({int(wait)}s)")
                await asyncio.sleep(wait)
                await scan_once(client, state, args.dry_run)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
