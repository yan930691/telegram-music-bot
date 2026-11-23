import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

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


class BlogAutoPoster:
    def __init__(
        self,
        bot: Bot,
        channel_id: str | int,
        rss_url: str,
        interval: int = 1800,
        bulk_mode: bool = False,
    ):
        self.bot = bot
        self.channel_id = channel_id
        # paginate လုပ်ဖို့ မူရင်း URL ကို သန့်ရှင်းအောင် လုပ်ထားတယ်
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

    # ---------- all posts (paginated) ----------
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

    # ---------- only new posts ----------
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

    # ---------- single entry ----------
    async def _handle_entry(self, session, entry):
        title = entry.get("title", "Untitled")
        summary = entry.get("summary", "") or ""
        if not summary and entry.get("content"):
            summary = entry["content"][0].get("value", "")
        source_link = entry.get("link", "")

        click_url = self._extract_click_here(summary)
        if not click_url:
            log.info("no link in %s", source_link)
            return

        cover_url = self._extract_cover(entry, summary)

        if "mediafire.com/folder/" in click_url:
            await self._handle_mediafire_folder(session, title, click_url, cover_url, source_link)
        else:
            direct = await self._resolve_file(session, click_url)
            if direct:
                await self._download_and_send(session, title, direct, cover_url, source_link)

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
    async def _handle_mediafire_folder(self, session, title, folder_url, cover_url, source_link):
        m = re.search(r'/folder/([a-zA-Z0-9]+)', folder_url)
        if not m:
            return
        fk = m.group(1)

        files, chunk = [], 1
        while True:
            api = (
                f"https://www.mediafire.com/api/1.4/folder/get_content.php"
                f"?folder_key={fk}&content_type=files&chunk={chunk}"
                f"&response_format=json&version=1.5"
            )
            async with session.get(api, headers={"User-Agent": USER_AGENT}, timeout=30) as r:
                data = await r.json(content_type=None)
            batch = data.get("response", {}).get("folder_content", {}).get("files", [])
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            chunk += 1
            await asyncio.sleep(2)

        log.info("folder %s: %d files", title, len(files))

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

        try:
            for f in files:
                name = f.get("filename", "")
                qk = f.get("quickkey")
                size = int(f.get("size", 0) or 0)
                if not qk or not name.lower().endswith((".mp3", ".m4a", ".flac")):
                    continue
                if size > MAX_TG_SIZE:
                    log.info("skip big: %s (%.1f MB)", name, size / 1024 / 1024)
                    continue
                direct = await self._resolve_mediafire_file(session, qk)
                if not direct:
                    continue
                await self._send_single(
                    session, os.path.splitext(name)[0], direct,
                    cover_path, title, source_link,
                )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _resolve_mediafire_file(self, session, quickkey):
        url = f"https://www.mediafire.com/file/{quickkey}"
        try:
            async with session.get(url, headers={"User-Agent": USER_AGENT}, timeout=30) as r:
                html = await r.text()
            soup = BeautifulSoup(html, "html.parser")
            btn = soup.find("a", id="downloadButton")
            if btn and btn.get("href"):
                return btn["href"]
            m = re.search(r'href="(https://download[^"]+\.mediafire\.com[^"]+)"', html)
            return m.group(1) if m else None
        except Exception:
            return None

    async def _resolve_file(self, session, url):
        if url.lower().endswith(".mp3"):
            return url
        if "mediafire.com/file/" in url:
            m = re.search(r'/file/([a-zA-Z0-9]+)', url)
            return await self._resolve_mediafire_file(session, m.group(1)) if m else None
        return None

    # ---------- send ----------
    async def _download_and_send(self, session, title, direct_url, cover_url, source_link):
        tmpdir = tempfile.mkdtemp(prefix="blog_")
        audio = os.path.join(tmpdir, "song.mp3")
        cover = None
        try:
            async with session.get(
                direct_url, headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=600),
            ) as r:
                r.raise_for_status()
                total = 0
                with open(audio, "wb") as f:
                    async for ch in r.content.iter_chunked(64 * 1024):
                        total += len(ch)
                        if total > MAX_TG_SIZE:
                            log.info("size exceeded: %s", title)
                            return
                        f.write(ch)
            if cover_url:
                cover = os.path.join(tmpdir, "cover.jpg")
                try:
                    async with session.get(
                        cover_url, headers={"User-Agent": USER_AGENT}, timeout=30
                    ) as cr:
                        if cr.status == 200:
                            with open(cover, "wb") as f:
                                f.write(await cr.read())
                        else:
                            cover = None
                except Exception:
                    cover = None
            await self._send_single(
                session, title, None, cover, None, source_link, local_audio=audio
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _send_single(self, session, title, direct_url, cover_path,
                           album=None, source_link=None, local_audio=None):
        tmpdir = None
        audio_path = local_audio
        try:
            if not audio_path:
                tmpdir = tempfile.mkdtemp(prefix="one_")
                audio_path = os.path.join(tmpdir, "a.mp3")
                async with session.get(
                    direct_url, headers={"User-Agent": USER_AGENT},
                    timeout=aiohttp.ClientTimeout(total=600),
                ) as r:
                    r.raise_for_status()
                    total = 0
                    with open(audio_path, "wb") as f:
                        async for ch in r.content.iter_chunked(64 * 1024):
                            total += len(ch)
                            if total > MAX_TG_SIZE:
                                return
                            f.write(ch)
            caption = f"<b>{album or title}</b>\n🎵 {title}"
            if source_link:
                caption += f'\n<a href="{source_link}">Source</a>'
            try:
                await self.bot.send_audio(
                    chat_id=self.channel_id,
                    audio=FSInputFile(audio_path, filename=f"{title[:50]}.mp3"),
                    title=title[:64],
                    performer=(album or "")[:64] or None,
                    thumbnail=FSInputFile(cover_path) if cover_path else None,
                    caption=caption[:1024],
                )
            except Exception:
                log.exception("send_audio failed: %s", title)
            await asyncio.sleep(3)
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)
