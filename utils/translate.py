# -*- coding: utf-8 -*-
"""English <-> Myanmar translation helpers for song search.

Uses Google's free (keyless) translate endpoints. The ``clients5``
dict-chrome endpoint is tried first because it is the most reliable, with the
``gtx`` endpoint and (if installed) ``deep-translator`` as fallbacks. All calls
are best-effort: if every provider fails we silently fall back to the original
text so uploads and searches never break.
"""
import asyncio
import logging
import re
import time

import aiohttp

try:  # optional last-resort fallback
    from deep_translator import GoogleTranslator
except Exception:  # pragma: no cover - optional dependency
    GoogleTranslator = None

# Myanmar Unicode (main block + extended) and Zawgyi-ish ranges.
_MYANMAR_RE = re.compile(r"[\u1000-\u109F\uAA60-\uAA7F\uA9E0-\uA9FF]")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Cache: (text, target) -> translated text or None
_CACHE = {}
_MAX_LEN = 480  # practical per-request limit for titles

# Simple global throttle so we stay under Google's ~5 req/sec free limit.
_MIN_INTERVAL = 0.35
_throttle_lock = asyncio.Lock()
_last_call = [0.0]


def detect_lang(text: str) -> str:
    """Return 'my' when the text contains Myanmar script, else 'en'."""
    if not text:
        return "en"
    return "my" if _MYANMAR_RE.search(text) else "en"


async def _throttle():
    async with _throttle_lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_call[0])
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call[0] = time.monotonic()


def _extract(data):
    """Normalise the different response shapes into a single string."""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        parts = []
        for item in data:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, list) and item and isinstance(item[0], str):
                parts.append(item[0])
        return "".join(parts) or None
    return None


async def _clients5(session, text, src, tgt):
    async with session.get(
        "https://clients5.google.com/translate_a/t",
        params={"client": "dict-chrome-ex", "sl": src, "tl": tgt, "q": text},
    ) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return _extract(await resp.json(content_type=None))


async def _gtx(session, text, src, tgt):
    async with session.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text},
    ) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        data = await resp.json(content_type=None)
        if data and isinstance(data, list) and data[0]:
            return "".join(seg[0] for seg in data[0] if seg and seg[0]) or None
        return None


def _deep_translator_sync(text, src, tgt):
    if not GoogleTranslator:
        return None
    try:
        return GoogleTranslator(source=src, target=tgt).translate(text)
    except Exception as e:
        logging.warning("deep-translator failed (%s->%s): %s", src, tgt, e)
        return None


async def translate(text: str, target: str):
    """Translate *text* into *target* ('my' or 'en'). Returns None on failure."""
    text = (text or "").strip()
    if not text or target not in ("my", "en"):
        return None
    key = (text, target)
    if key in _CACHE:
        return _CACHE[key]
    src = "en" if target == "my" else "my"
    snippet = text[:_MAX_LEN]

    result = None
    try:
        async with aiohttp.ClientSession(
            headers={"User-Agent": _USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as session:
            for name, fn in (("clients5", _clients5), ("gtx", _gtx)):
                for _ in range(2):
                    await _throttle()
                    try:
                        result = await fn(session, snippet, src, target)
                        if result:
                            break
                    except Exception as e:
                        logging.warning("translate %s failed (%s->%s): %s",
                                        name, src, target, str(e)[:120])
                if result:
                    break
    except Exception:
        logging.exception("translate session failed")

    if not result:
        result = await asyncio.to_thread(_deep_translator_sync, snippet, src, target)

    if result:
        result = result.strip()
    # Treat unchanged / empty output (numbers, already-correct, failed) as no-op.
    if not result or result.lower() == text.lower():
        result = None
    _CACHE[key] = result
    return result


async def alt_name(text: str):
    """Return (translated_text, target_lang) into the *other* language."""
    if not text:
        return None, None
    target = "en" if detect_lang(text) == "my" else "my"
    return await translate(text, target), target


async def build_search_terms(title="", artist="", album=""):
    """Build the lower-cased list of strings a song should be findable by:
    the original title/artist/album plus their other-language translations."""
    terms = set()
    for value in (title, artist, album):
        if value and value.strip():
            terms.add(value.strip().lower())
    for value in (title, artist, album):
        if value and value.strip():
            alt, _ = await alt_name(value)
            if alt:
                terms.add(alt.strip().lower())
    return sorted(terms)
