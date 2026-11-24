import asyncio
import json
import logging
import os
import random
import re
import shutil
import tempfile
from html import escape as html_escape

import aiohttp
import feedparser
from aiogram import Bot
from aiogram.types import FSInputFile
from bs4 import BeautifulSoup

from services.blog_state import BlogState

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
MAX_TG_SIZE = int(os.getenv("MAX_TG_SIZE_MB", "50")) * 1024 * 1024
BLOGGER_PAGE = 500
AUDIO_EXTS = (".mp3", ".m4a", ".flac", ".ogg", ".wav")
DAILY_LIMIT = int(os.getenv("BLOG_DAILY_LIMIT", "10"))

# ⬇️⬇️⬇️ NEW: Proxy configuration
PROXY_LIST_URL = "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/all/data.json"
# သင့်ကိုယ်ပိုင် proxy ရှိရင် ဒီမှာ ထည့်ပါ (ဥပမာ - "http://user:pass@host:port")
CUSTOM_PROXY = os.getenv("BLOG_PROXY_URL", "").strip()
PROXY_TIMEOUT = 10
# ⬆️⬆️⬆️ NEW


def _safe_decode(raw: bytes) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


# ⬇️⬇️⬇️ NEW: Proxy helpers
async def fetch_proxy_list(session: aiohttp.ClientSession) -> list[dict]:
    """Download a fresh list of free proxies."""
    try:
        async with session.get(
            PROXY_LIST_URL,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as r:
            data = await r.json(content_type=None)
        proxies = data.get("proxies", data) if isinstance(data, dict) else data
        if isinstance(proxies, list):
            log.info("Loaded %d free proxies", len(proxies))
            return proxies
    except Exception as e:
        log.warning("Failed to fetch proxy list: %s", e)
    return []


async def test_proxy(proxy: dict, target_url: str = "https://www.mediafire.com") -> bool:
    """Quickly test if a proxy works by hitting MediaFire."""
    proxy_url = proxy.get("proxy") or f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                target_url,
                proxy=proxy_url,
                headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT),
                allow_redirects=True,
            ) as r:
                return r.status == 200
    except Exception:
        return False


async def find_working_proxy() -> str | None:
    """Try free proxies until one works. Returns proxy URL or None."""
    if CUSTOM_PROXY:
        log.info("Using custom proxy from env: %s", CUSTOM_PROXY.split("@")[-1])
        return CUSTOM_PROXY

    async with aiohttp.ClientSession() as session:
        proxies = await fetch_proxy_list(session)

    if not proxies:
        log.warning("No free proxies available")
        return None

    random.shuffle(proxies)
    # Try max 20 proxies
    for i, proxy in enumerate(proxies[:20], 1):
        proxy_url = proxy.get("proxy") or f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
        log.info("Testing proxy %d/20: %s", i, proxy_url.split("@")[-1])
        if await test_proxy(proxy):
            log.info("  ✓ working proxy found: %s", proxy_url.split("@")[-1])
            return proxy_url
        await asyncio.sleep(1)

    log.warning("No working proxy found after trying 20")
    return None
# ⬆️⬆️⬆️ NEW


class BlogAutoPoster:
    def __init__(self, bot: Bot, channel_id, rss_url: str):
        self.bot = bot
        self.channel_id = channel_id
        self.rss_url = rss_url.split("&start-index")[0].split("&max-results")[0]
        self.state = BlogState()
        self._seen: set[str] = set()
        self._lock = asyncio.Lock()
        self._running = False
        self._proxy_url: str | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def load_seen(self):
        self._seen = await self.state.load_all()
        log.info("Loaded %d seen posts", len(self._seen))

    async def reload_seen(self):
        self._seen = await self.state.load_all()
        log.info("Reloaded %d seen posts", len(self._seen))

    async def get_status(self) -> dict:
        return {
            "today_count": await self.state.get_daily_count(),
            "seen_count": await self.state.seen_count(),
            "daily_limit": DAILY_LIMIT,
            "running": self._running,
            "proxy": self._proxy_url.split("@")[-1] if self._proxy_url else None,
        }

    # ---------- batch processing ----------
    async def process_batch(self, count: int = 10) -> dict:
        async with self._lock:
            if self._running:
                return {"ok": False, "reason": "already_running"}
            self._running = True
            try:
                return await self._process_batch_inner(count)
            finally:
                self._running = False

    async def _process_batch_inner(self, count: int) -> dict:
        used = await self.state.get_daily_count()
        if used >= DAILY_LIMIT:
            return {
                "ok": False,
                "reason": "daily_limit",
                "used": used,
                "limit": DAILY_LIMIT,
            }

        # ⬇️⬇️⬇️ NEW: Find a working proxy before starting batch
        log.info("Searching for a working proxy...")
        self._proxy_url = await find_working_proxy()
        if not self._proxy_url:
            log.warning("No proxy available — MediaFire may block requests")
        else:
            log.info("Batch will use proxy: %s", self._proxy_url.split("@")[-1])
        # ⬆️⬆️⬆️ NEW

        remaining = DAILY_LIMIT - used
        batch_size = min(count, remaining)

        entries = await self._fetch_all_entries()
        entries.reverse()
        unprocessed = [
            e for e in entries
            if e.get("link") and e["link"] not in self._seen
        ][:batch_size]

        if not unprocessed:
            return {
                "ok": True,
                "processed": 0,
                "failed": 0,
                "reason": "nothing_new",
                "used": used,
            }

        log.info(
            "Processing batch: %d/%d posts (daily: %d/%d)",
            len(unprocessed), batch_size, used, DAILY_LIMIT,
        )

        processed = failed = 0
        # ⬇️⬇️⬇️ NEW: pass proxy to session
        connector = aiohttp.TCPConnector(ssl=False) if self._proxy_url else None
        async with aiohttp.ClientSession(connector=connector) as session:
            for i, entry in enumerate(unprocessed, 1):
                title = entry.get("title", "?")
                log.info("[%d/%d] %s", i, len(unprocessed), title)

                try:
                    ok = await self._handle_entry(session, entry)
                    if ok:
                        self._seen.add(entry["link"])
                        await self.state.mark(entry["link"])
                        await self.state.increment_daily()
                        processed += 1
                        log.info("  ✓ entry posted successfully")
                    else:
                        failed += 1
                        log.warning("  ✗ entry failed (will retry next batch)")
                except Exception:
                    log.exception("entry exception: %s", entry.get("link"))
                    failed += 1

                await asyncio.sleep(5)
        # ⬆️⬆️⬆️ NEW

        return {
            "ok": True,
            "processed": processed,
            "failed": failed,
            "used": await self.state.get_daily_count(),
            "limit": DAILY_LIMIT,
        }

    # ---------- fetch entries ----------
    async def _fetch_all_entries(self) -> list:
        all_entries = []
        start = 1
        while True:
            url = f"{self.rss_url}&max-results={BLOGGER_PAGE}&start-index={start}"
            feed = await asyncio.to_thread(feedparser.parse, url)
            if not feed.entries:
                break
            all_entries.extend(feed.entries)
            if len(feed.entries) < BLOGGER_PAGE:
                break
            start += BLOGGER_PAGE
            await asyncio.sleep(2)
        return all_entries

    # ---------- dispatch ----------
    async def _handle_entry(self, session, entry) -> bool:
        title = entry.get("title", "Untitled")
        source_link = entry.get("link", "")

        summary = entry.get("summary", "") or ""
        if not summary and entry.get("content"):
            summary = entry["content"][0].get("value", "")

        click_url = self._extract_download_link(summary)

        if not click_url and source_link:
            log.info("  no link in summary, fetching post page...")
            try:
                async with session.get(
                    source_link,
                    headers={"User-Agent": USER_AGENT},
                    timeout=30,
                ) as r:
                    if r.status == 200:
                        raw = await r.read()
                        html = _safe_decode(raw)
                        soup = BeautifulSoup(html, "html.parser")
                        body = soup.find("div", class_="post-body") or soup
                        click_url = self._extract_download_link(str(body))
            except Exception as e:
                log.warning("  post fetch failed: %s", e)

        if not click_url:
            log.info("  -> no download link found")
            return False

        cover_url = self._extract_cover(entry, summary)

        if "mediafire.com/folder/" in click_url:
            return await self._handle_mediafire_folder(
                session, title, click_url, cover_url, source_link
            )
        elif "mediafire.com/file/" in click_url:
            m = re.search(r'/file/([a-zA-Z0-9]+)', click_url)
            if m:
                direct = await self._resolve_mediafire_file(session, m.group(1))
                if direct:
                    return await self._send_single(
                        session, title, direct, cover_url, None, source_link
                    )
        else:
            log.info("  -> unsupported host: %s", click_url)
        return False

    # ---------- HTML helpers ----------
    @staticmethod
    def _extract_download_link(html: str) -> str | None:
        for host in ("mediafire.com", "pcloud.link", "u.pcloud.link"):
            m = re.search(
                rf'href="([^"]*{re.escape(host)}[^"]*)"',
                html, re.IGNORECASE,
            )
            if m:
                return m.group(1).replace("&amp;", "&")
        m = re.search(
            r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:<[^>]+>)*\s*Click\s*Here',
            html, re.IGNORECASE,
        )
        if m:
            return m.group(1).replace("&amp;", "&")
        return None

    @staticmethod
    def _extract_cover(entry, html):
        for k in ("media_thumbnail", "media_content"):
            for it in (entry.get(k) or []):
                if it.get("url"):
                    return it["url"]
        m = re.search(r'<img[^>]+src="([^"]+)"', html)
        return m.group(1) if m else None

    # ---------- MediaFire folder ----------
    async def _handle_mediafire_folder(
        self, session, title, folder_url, cover_url, source_link
    ) -> bool:
        m = re.search(r'/folder/([a-zA-Z0-9]+)', folder_url)
        if not m:
            return False
        fk = m.group(1)

        files, chunk = [], 1
        while True:
            api = (
                f"https://www.mediafire.com/api/1.4/folder/get_content.php"
                f"?folder_key={fk}&content_type=files&chunk={chunk}"
                f"&response_format=json&version=1.5"
            )
            data = {}
            for use_proxy in (True, False):
                proxy = self._proxy_url if use_proxy else None
                if not use_proxy and not self._proxy_url:
                    continue
                try:
                    async with session.get(
                        api,
                        headers={
                            "User-Agent": USER_AGENT,
                            "Accept-Encoding": "identity",
                        },
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=45),
                    ) as r:
                        raw = await r.read()
                    data = json.loads(_safe_decode(raw)) if raw else {}
                    break
                except Exception as e:
                    log.warning("  folder API %s failed: %s %s",
                                "proxy" if use_proxy else "direct",
                                type(e).__name__, e)
            if not data:
                break
            batch = (
                data.get("response", {})
                .get("folder_content", {})
                .get("files", [])
            )
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            chunk += 1
            await asyncio.sleep(2)

        if not files:
            log.info("  -> folder has 0 files")
            return False

        log.info("  folder: %d file(s)", len(files))

        tmpdir = tempfile.mkdtemp(prefix="mf_")
        cover_path = None
        if cover_url:
            try:
                cover_path = os.path.join(tmpdir, "cover.jpg")
                async with session.get(
                    cover_url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=30,
                ) as cr:
                    if cr.status == 200:
                        with open(cover_path, "wb") as f:
                            f.write(await cr.read())
                    else:
                        cover_path = None
            except Exception:
                cover_path = None

        # Post the album cover first, then the tracks underneath it.
        cover_msg_id = None
        if cover_path and os.path.exists(cover_path):
            try:
                caption = f"<b>{html_escape(title, quote=False)}</b>"
                if source_link:
                    caption += (
                        f'\n<a href="{html_escape(source_link, quote=True)}">'
                        f"Source</a>"
                    )
                cover_msg = await self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=FSInputFile(cover_path),
                    caption=caption[:1024],
                    parse_mode="HTML",
                )
                cover_msg_id = getattr(cover_msg, "message_id", None)
                log.info("  cover photo posted")
            except Exception as e:
                log.warning("  cover photo failed: %s %s", type(e).__name__, e)

        posted = 0
        try:
            for f in files:
                name = f.get("filename", "")
                qk = f.get("quickkey")
                size = int(f.get("size", 0) or 0)

                if not qk or not name.lower().endswith(AUDIO_EXTS):
                    continue
                if size > MAX_TG_SIZE:
                    log.info("    skip (big): %s (%.1f MB)",
                             name, size / 1024 / 1024)
                    continue

                direct = await self._resolve_mediafire_file(session, qk)
                if not direct:
                    log.warning("    FAIL: %s (no direct link)", name)
                    continue

                ok = await self._send_single(
                    session, os.path.splitext(name)[0], direct,
                    cover_path, title, source_link,
                )
                if ok:
                    posted += 1
                    log.info("    POSTED: %s", name)
                await asyncio.sleep(3)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        # No track made it -- remove the cover so a retry won't duplicate it.
        if posted == 0 and cover_msg_id:
            try:
                await self.bot.delete_message(
                    chat_id=self.channel_id, message_id=cover_msg_id,
                )
                log.info("  cover photo removed (no tracks posted)")
            except Exception as e:
                log.debug("  cover cleanup failed: %s", e)

        log.info("  folder done: %d posted", posted)
        return posted > 0

    # ---------- MediaFire direct link (proxy-aware) ----------
    async def _resolve_mediafire_file(self, session, quickkey) -> str | None:
        # Strategy 1: API
        try:
            api = (
                f"https://www.mediafire.com/api/1.5/file/get_links.php"
                f"?quick_key={quickkey}&link_type=direct_download"
                f"&response_format=json"
            )
            async with session.get(
                api,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Encoding": "identity",
                },
                proxy=self._proxy_url,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                raw = await r.read()
            text = _safe_decode(raw) if raw else ""
            data = json.loads(text) if text.strip() else {}
            resp = data.get("response", {})
            for link in resp.get("links", []):
                dl = link.get("direct_download")
                if dl:
                    log.debug("  [API OK] %s", quickkey)
                    return dl
            log.debug(
                "  [API] result=%s msg=%s",
                resp.get("result"), str(resp.get("message", ""))[:80],
            )
        except Exception as e:
            log.debug("  [API] failed: %s %s", type(e).__name__, e)

        # Strategy 2: the file page redirects straight to the CDN download URL.
        # Following that redirect makes aiohttp hand us MP3 bytes, not HTML, so
        # the old downloadButton regex could never match.  Read Location first.
        # If the proxy stalls, retry once without it -- a dead proxy used to
        # burn the whole 30s budget and lose the file.
        url = f"https://www.mediafire.com/file/{quickkey}"
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": "https://www.mediafire.com/",
        }
        attempts = [(True, self._proxy_url)]
        if self._proxy_url:
            attempts.append((False, None))
        for use_proxy, proxy in attempts:
            try:
                async with session.get(
                    url,
                    headers=headers,
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=60),
                    allow_redirects=False,
                ) as r:
                    status = r.status
                    location = (r.headers.get("Location") or "").strip()
                    content_type = r.headers.get("Content-Type", "?")
                    if status in (301, 302, 303, 307, 308) and location:
                        if location.startswith("//"):
                            location = "https:" + location
                        if location.startswith(("http://", "https://")):
                            log.debug("  [REDIRECT OK] %s via %s", quickkey,
                                      "proxy" if use_proxy else "direct")
                            return location.replace("&amp;", "&")
                    raw = await r.read()

                page = _safe_decode(raw)
                log.debug(
                    "  [HTML] status=%s ct=%s bytes=%d",
                    status, content_type, len(raw),
                )

                m = re.search(r'id="downloadButton"[^>]*href="([^"]+)"', page)
                if not m:
                    m = re.search(r'href="([^"]+)"[^>]*id="downloadButton"', page)
                if m:
                    log.debug("  [HTML OK] button found")
                    return m.group(1).replace("&amp;", "&")

                m = re.search(r'(https://download\d+\.mediafire\.com/[^"\'\s]+)', page)
                if m:
                    log.debug("  [HTML OK] direct link found")
                    return m.group(1).replace("&amp;", "&")

                low = page.lower()
                if status != 200:
                    log.warning("  [HTML] HTTP %s (%s)", status, quickkey)
                elif "captcha" in low or "are you a robot" in low:
                    log.warning("  [HTML] CAPTCHA page (%s)", quickkey)
                elif (
                    "file removed" in low
                    or "file deleted" in low
                    or "invalid or deleted" in low
                ):
                    log.warning("  [HTML] file removed/deleted (%s)", quickkey)
                elif len(raw) < 500:
                    log.warning(
                        "  [HTML] tiny response (%d bytes, %s): %r",
                        len(raw), content_type, raw[:120],
                    )
                else:
                    log.warning(
                        "  [HTML] no download button (len=%d, ct=%s, %s)",
                        len(raw), content_type, quickkey,
                    )
                # Got a real page but no link -- no point retrying.
                return None
            except Exception as e:
                log.warning("  [HTML] %s failed: %s %s",
                            "proxy" if use_proxy else "direct",
                            type(e).__name__, e)

        return None

    # ---------- download + send (proxy-aware download) ----------
    async def _send_single(
        self, session, title, direct_url, cover_path,
        album=None, source_link=None,
    ) -> bool:
        tmpdir = tempfile.mkdtemp(prefix="one_")
        audio_path = os.path.join(tmpdir, "a.mp3")
        try:
            downloaded = False
            for use_proxy in (True, False):
                proxy = self._proxy_url if use_proxy else None
                if not use_proxy and not self._proxy_url:
                    continue
                try:
                    async with session.get(
                        direct_url,
                        headers={"User-Agent": USER_AGENT},
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=600),
                    ) as r:
                        r.raise_for_status()
                        total = 0
                        with open(audio_path, "wb") as f:
                            async for ch in r.content.iter_chunked(64 * 1024):
                                total += len(ch)
                                if total > MAX_TG_SIZE:
                                    log.info("    download > 50MB, skip")
                                    return False
                                f.write(ch)
                    downloaded = True
                    break
                except Exception as e:
                    log.warning("    download %s failed: %s %s",
                                "proxy" if use_proxy else "direct",
                                type(e).__name__, e)
            if not downloaded:
                return False

            # Folder flow passes a local temp file; direct-file flow passes a
            # URL.  FSInputFile needs a real path, so download URL covers first.
            cover_file = cover_path
            if cover_path and str(cover_path).startswith(("http://", "https://")):
                cover_file = None
                try:
                    async with session.get(
                        str(cover_path),
                        headers={"User-Agent": USER_AGENT},
                        proxy=self._proxy_url,
                        timeout=30,
                    ) as cr:
                        if cr.status == 200:
                            cover_file = os.path.join(tmpdir, "cover.jpg")
                            with open(cover_file, "wb") as f:
                                f.write(await cr.read())
                except Exception as e:
                    log.debug("    cover download failed: %s", e)
                    cover_file = None

            safe_album = html_escape(album or title, quote=False)
            safe_title = html_escape(title, quote=False)
            caption = f"<b>{safe_album}</b>\n🎵 {safe_title}"
            if source_link:
                caption += f'\n<a href="{html_escape(source_link, quote=True)}">Source</a>'

            try:
                await self.bot.send_audio(
                    chat_id=self.channel_id,
                    audio=FSInputFile(audio_path, filename=f"{title[:50]}.mp3"),
                    title=title[:64],
                    performer=(album or "")[:64] or None,
                    thumbnail=FSInputFile(cover_file) if cover_file else None,
                    caption=caption[:1024],
                )
                return True
            except Exception as e:
                log.warning("    send_audio failed: %s", e)
                return False
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
