import asyncio
import logging
import os
import re
import shutil
import tempfile

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


class BlogAutoPoster:
    def __init__(
        self,
        bot: Bot,
        channel_id,
        rss_url: str,
        interval: int = 1800,
        bulk_mode: bool = False,
    ):
        self.bot = bot
        self.channel_id = channel_id
        self.rss_url = rss_url.split("&start-index")[0].split("&max-results")[0]
        self.interval = interval
        self.bulk_mode = bulk_mode
        self.state = BlogState()
        self._seen: set[str] = set()
        self._stop = asyncio.Event()

    # ---------- entry ----------
    async def run(self):
        self._seen = await self.state.load_all()
        log.info("Blog poster start: %d seen, bulk=%s", len(self._seen), self.bulk_mode)
        if self.bulk_mode:
            await self._bulk_all()
            log.info("Bulk mode finished. Switching to poll mode.")
        while not self._stop.is_set():
            try:
                await self._poll_new()
            except Exception:
                log.exception("poll failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass

    def stop(self):
        self._stop.set()

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
            log.info("fetched %d (total %d)", len(feed.entries), len(all_entries))
            if len(feed.entries) < BLOGGER_PAGE:
                break
            start += BLOGGER_PAGE
            await asyncio.sleep(3)
        return all_entries

    async def _bulk_all(self):
        entries = await self._fetch_all_entries()
        log.info("TOTAL entries: %d", len(entries))
        entries.reverse()
        async with aiohttp.ClientSession() as session:
            for i, entry in enumerate(entries, 1):
                if self._stop.is_set():
                    break
                link = entry.get("link")
                if not link or link in self._seen:
                    continue
                log.info("[%d/%d] %s", i, len(entries), entry.get("title", "?"))
                try:
                    await self._handle_entry(session, entry)
                    self._seen.add(link)
                    await self.state.mark(link)
                except Exception:
                    log.exception("entry failed: %s", link)
                await asyncio.sleep(5)

    async def _poll_new(self):
        feed = await asyncio.to_thread(feedparser.parse, self.rss_url)
        new = [e for e in feed.entries if e.get("link") and e["link"] not in self._seen]
        if not new:
            return
        new.reverse()
        async with aiohttp.ClientSession() as session:
            for entry in new:
                try:
                    await self._handle_entry(session, entry)
                    self._seen.add(entry["link"])
                    await self.state.mark(entry["link"])
                except Exception:
                    log.exception("entry failed")
                await asyncio.sleep(5)

    # ---------- dispatch ----------
    async def _handle_entry(self, session, entry):
        title = entry.get("title", "Untitled")
        summary = entry.get("summary", "") or ""
        if not summary and entry.get("content"):
            summary = entry["content"][0].get("value", "")
        source_link = entry.get("link", "")

        click_url = self._extract_click_here(summary)
        if not click_url:
            log.info("no download link in %s", source_link)
            return

        cover_url = self._extract_cover(entry, summary)

        if "mediafire.com/folder/" in click_url:
            await self._handle_mediafire_folder(
                session, title, click_url, cover_url, source_link
            )
        elif "mediafire.com/file/" in click_url:
            m = re.search(r'/file/([a-zA-Z0-9]+)', click_url)
            if m:
                direct = await self._resolve_mediafire_file(session, m.group(1))
                if direct:
                    await self._send_single(
                        session, title, direct, cover_url, None, source_link
                    )
        else:
            log.info("unsupported host: %s", click_url)

    # ---------- HTML helpers ----------
    @staticmethod
    def _extract_click_here(html):
        m = re.search(
            r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:<[^>]+>)*\s*(?:Mediafire|MediaFire|Download)?\s*Link?',
            html, re.IGNORECASE,
        )
        if m:
            return m.group(1)
        for host in ("mediafire.com", "pcloud.link", "u.pcloud.link"):
            m = re.search(rf'href="(https?://[^"]*{re.escape(host)}[^"]*)"', html)
            if m:
                return m.group(1)
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
    ):
        m = re.search(r'/folder/([a-zA-Z0-9]+)', folder_url)
        if not m:
            log.warning("folder key not found in %s", folder_url)
            return
        fk = m.group(1)

        # fetch all file entries via MediaFire API (paginated)
        files, chunk = [], 1
        while True:
            api = (
                f"https://www.mediafire.com/api/1.4/folder/get_content.php"
                f"?folder_key={fk}&content_type=files&chunk={chunk}"
                f"&response_format=json&version=1.5"
            )
            try:
                async with session.get(
                    api, headers={"User-Agent": USER_AGENT}, timeout=30
                ) as r:
                    data = await r.json(content_type=None)
            except Exception as e:
                log.warning("folder API failed (folder=%s): %s", fk, e)
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

        log.info("folder '%s': %d file(s)", title, len(files))
        if not files:
            return

        # download cover once per folder
        tmpdir = tempfile.mkdtemp(prefix="mf_")
        cover_path = None
        if cover_url:
            try:
                cover_path = os.path.join(tmpdir, "cover.jpg")
                async with session.get(
                    cover_url, headers={"User-Agent": USER_AGENT}, timeout=30
                ) as cr:
                    if cr.status == 200:
                        with open(cover_path, "wb") as f:
                            f.write(await cr.read())
                    else:
                        cover_path = None
            except Exception:
                cover_path = None

        posted = skipped = 0
        try:
            for idx, f in enumerate(files, 1):
                name = f.get("filename", "?")
                qk = f.get("quickkey")
                size = int(f.get("size", 0) or 0)

                log.info(
                    "  [%d/%d] %s (%.1f MB)",
                    idx, len(files), name, size / 1024 / 1024,
                )

                if not qk:
                    log.info("    -> skip: no quickkey")
                    skipped += 1
                    continue
                if not name.lower().endswith(AUDIO_EXTS):
                    log.info("    -> skip: not audio")
                    skipped += 1
                    continue
                if size > MAX_TG_SIZE:
                    log.info(
                        "    -> skip: %.1f MB > 50 MB limit",
                        size / 1024 / 1024,
                    )
                    skipped += 1
                    continue

                direct = await self._resolve_mediafire_file(session, qk)
                if not direct:
                    log.warning(
                        "    -> FAIL: no direct link (quickkey=%s)", qk
                    )
                    skipped += 1
                    continue

                log.info("    -> direct link OK")
                ok = await self._send_single(
                    session,
                    os.path.splitext(name)[0],
                    direct,
                    cover_path,
                    title,
                    source_link,
                )
                if ok:
                    posted += 1
                    log.info("    -> POSTED")
                else:
                    skipped += 1
                    log.warning("    -> FAIL: send failed")

                await asyncio.sleep(3)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        log.info(
            "folder done: '%s' -> posted=%d, skipped=%d",
            title, posted, skipped,
        )

    # ---------- MediaFire direct link ----------
    async def _resolve_mediafire_file(self, session, quickkey):
        # Try MediaFire API first
        api_url = (
            f"https://www.mediafire.com/api/1.5/file/get_links.php"
            f"?quick_key={quickkey}&link_type=direct_download"
            f"&response_format=json"
        )
        try:
            async with session.get(
                api_url, headers={"User-Agent": USER_AGENT}, timeout=30
            ) as r:
                text = await r.text()
            data = None
            try:
                data = __import__("json").loads(text)
            except Exception:
                pass
            if data:
                resp = data.get("response", {})
                if resp.get("result") == "Success" or "links" in resp:
                    for link in resp.get("links", []):
                        dl = link.get("direct_download")
                        if dl:
                            return dl
        except Exception as e:
            log.debug("MF API failed (%s): %s", quickkey, e)

        # Fallback: HTML scrape
        url = f"https://www.mediafire.com/file/{quickkey}"
        try:
            async with session.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            ) as r:
                status = r.status
                html = await r.text()
            log.debug("MF page status=%s len=%d", status, len(html))

            soup = BeautifulSoup(html, "html.parser")
            btn = soup.find("a", id="downloadButton")
            if btn and btn.get("href"):
                return btn["href"]

            m = re.search(
                r'href="(https://download[^"]+\.mediafire\.com[^"]+)"', html
            )
            if m:
                return m.group(1)

            # last resort: any download.* link
            m = re.search(r'(https://download\d+\.mediafire\.com/[^"\'\s]+)', html)
            if m:
                return m.group(1)

            # nothing — log reason
            if "captcha" in html.lower() or "are you a robot" in html.lower():
                log.warning("    MF returned CAPTCHA page (%s)", quickkey)
            elif status != 200:
                log.warning("    MF returned HTTP %s (%s)", status, quickkey)
            else:
                log.warning(
                    "    MF page loaded but no download button (%s)", quickkey
                )
        except Exception as e:
            log.warning("    MF scrape error (%s): %s", quickkey, e)

        return None

    # ---------- download + send ----------
    async def _send_single(
        self,
        session,
        title,
        direct_url,
        cover_path,
        album=None,
        source_link=None,
        local_audio=None,
    ) -> bool:
        tmpdir = None
        audio_path = local_audio
        try:
            if not audio_path:
                tmpdir = tempfile.mkdtemp(prefix="one_")
                audio_path = os.path.join(tmpdir, "a.mp3")
                try:
                    async with session.get(
                        direct_url,
                        headers={"User-Agent": USER_AGENT},
                        timeout=aiohttp.ClientTimeout(total=600),
                    ) as r:
                        r.raise_for_status()
                        total = 0
                        with open(audio_path, "wb") as f:
                            async for ch in r.content.iter_chunked(64 * 1024):
                                total += len(ch)
                                if total > MAX_TG_SIZE:
                                    log.info(
                                        "    download exceeded 50 MB, abort"
                                    )
                                    return False
                                f.write(ch)
                    log.info(
                        "    downloaded %.1f MB", total / 1024 / 1024
                    )
                except Exception as e:
                    log.warning("    download failed: %s", e)
                    return False

            caption = f"<b>{album or title}</b>\n🎵 {title}"
            if source_link:
                caption += f'\n<a href="{source_link}">Source</a>'

            try:
                await self.bot.send_audio(
                    chat_id=self.channel_id,
                    audio=FSInputFile(
                        audio_path, filename=f"{title[:50]}.mp3"
                    ),
                    title=title[:64],
                    performer=(album or "")[:64] or None,
                    thumbnail=(
                        FSInputFile(cover_path) if cover_path else None
                    ),
                    caption=caption[:1024],
                )
                return True
            except Exception as e:
                log.warning("    send_audio failed: %s", e)
                return False
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)
