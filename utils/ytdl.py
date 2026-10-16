"""Media resolution + download for voice-chat streaming.

Supports any URL understood by yt-dlp (YouTube, YouTube Music, SoundCloud,
Bandcamp, direct links, ...) plus plain text search, and Spotify links via the
official Web API (when client credentials are configured), the public Odesli
(song.link) API, or finally the public Spotify oEmbed endpoint.
"""

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass

import aiohttp
import yt_dlp

from config import (
    DOWNLOADS_DIR,
    COOKIES_FILE,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
)

log = logging.getLogger("ytdl")

URL_RE = re.compile(r"^https?://", re.I)
SPOTIFY_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z-]+/)?(track|album|playlist|artist)/([A-Za-z0-9]+)"
)
YOUTUBE_RE = re.compile(r"(youtube\.com|youtu\.be|music\.youtube\.com)", re.I)


class ResolveError(Exception):
    """Raised when a query/URL cannot be resolved to playable media."""


@dataclass
class Track:
    id: str
    title: str = "Unknown"
    url: str = ""
    duration_sec: int = 0
    duration: str = "00:00"
    thumbnail: str = ""
    file_path: str = None
    requester: str = ""
    requester_id: int = 0
    video: bool = False


class _DummyLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def _base_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "logger": _DummyLogger(),
        "restrictfilenames": False,
    }
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    return opts


def fmt_duration(seconds) -> str:
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        return "00:00"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _to_track(entry: dict, requester: str = "", video: bool = False) -> Track | None:
    if not entry:
        return None
    vid = entry.get("id")
    url = entry.get("webpage_url") or entry.get("url")
    if not vid or not url:
        return None
    thumb = entry.get("thumbnail")
    if not thumb:
        thumbs = entry.get("thumbnails") or []
        if thumbs:
            thumb = thumbs[-1].get("url")
    dur = entry.get("duration") or 0
    return Track(
        id=str(vid),
        title=(entry.get("title") or "Unknown")[:80],
        url=url,
        duration_sec=int(dur or 0),
        duration=fmt_duration(dur),
        thumbnail=thumb or "",
        requester=requester,
        video=video,
    )


def _extract_sync(target: str, limit: int = 1) -> list[dict]:
    opts = _base_opts()
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False)
    if not info:
        return []
    entries = info.get("entries")
    if entries:
        return [e for e in entries if e][:limit]
    return [info]


async def _extract(target: str, limit: int = 1) -> list[dict]:
    return await asyncio.to_thread(_extract_sync, target, limit)


# --------------------------- Spotify resolution ---------------------------

async def _spotify_token() -> str | None:
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json()
                return data.get("access_token")
    except Exception as e:
        log.warning("Spotify token failed: %s", e)
        return None


def _spotify_track_from_item(item: dict) -> dict | None:
    if not item:
        return None
    name = item.get("name")
    artists = ", ".join(a.get("name", "") for a in (item.get("artists") or []) if a)
    if not name:
        return None
    return {"title": name, "artist": artists}


async def _spotify_official(kind: str, sid: str) -> list[dict]:
    token = await _spotify_token()
    if not token:
        raise ResolveError("no-token")
    headers = {"Authorization": f"Bearer {token}"}
    out: list[dict] = []
    async with aiohttp.ClientSession(headers=headers) as s:
        timeout = aiohttp.ClientTimeout(total=25)
        if kind == "track":
            r = await s.get(f"https://api.spotify.com/v1/tracks/{sid}", timeout=timeout)
            d = await r.json()
            t = _spotify_track_from_item(d)
            if t:
                out.append(t)
        elif kind == "album":
            r = await s.get(f"https://api.spotify.com/v1/albums/{sid}", timeout=timeout)
            d = await r.json()
            for it in (d.get("tracks") or {}).get("items", []):
                # album track items reuse "artists"
                t = _spotify_track_from_item(it)
                if t:
                    out.append(t)
        elif kind == "playlist":
            r = await s.get(
                f"https://api.spotify.com/v1/playlists/{sid}/tracks?limit=30",
                timeout=timeout,
            )
            d = await r.json()
            for it in d.get("items", []):
                t = _spotify_track_from_item(it.get("track") or {})
                if t:
                    out.append(t)
    if not out:
        raise ResolveError("empty")
    return out


async def _spotify_odesli(url: str) -> list[dict]:
    async with aiohttp.ClientSession() as s:
        async with s.get(
            "https://api.song.link/v1-alpha.1/links",
            params={"url": url},
            timeout=aiohttp.ClientTimeout(total=25),
        ) as resp:
            data = await resp.json()
    ent = data.get("entitiesByUniqueId", {})
    eid = data.get("entityUniqueId")
    e = ent.get(eid) or {}
    title = e.get("title")
    artist = e.get("artistName", "")
    if not title:
        raise ResolveError("odesli-empty")
    return [{"title": title, "artist": artist}]


async def _spotify_oembed(url: str) -> list[dict]:
    async with aiohttp.ClientSession() as s:
        async with s.get(
            "https://open.spotify.com/oembed",
            params={"url": url},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            data = await resp.json()
    title = data.get("title")
    if not title:
        raise ResolveError("oembed-empty")
    return [{"title": title, "artist": ""}]


async def _spotify_meta(url: str) -> list[dict]:
    m = SPOTIFY_RE.search(url)
    if not m:
        raise ResolveError("bad-spotify-url")
    kind, sid = m.group(1), m.group(2)
    # Best -> worst: official API, Odesli, oEmbed (single track only).
    for resolver in (_spotify_official, _spotify_odesli):
        try:
            return await resolver(kind, sid)
        except ResolveError:
            continue
        except Exception as e:
            log.warning("Spotify resolver %s failed: %s", resolver.__name__, e)
            continue
    try:
        return await _spotify_oembed(url)
    except Exception as e:
        log.warning("Spotify oEmbed failed: %s", e)
        raise ResolveError("spotify-failed")


# ------------------------------- Public API -------------------------------

async def resolve(text_or_url: str, video: bool = False, requester: str = "") -> list[Track]:
    """Resolve a URL or search query into one or more playable Tracks."""
    text_or_url = (text_or_url or "").strip()
    if not text_or_url:
        raise ResolveError("empty")

    tracks: list[Track] = []

    if SPOTIFY_RE.search(text_or_url):
        metas = await _spotify_meta(text_or_url)
        for meta in metas[:20]:
            q = " ".join(p for p in (meta.get("artist"), meta.get("title")) if p)
            try:
                entries = await _extract(f"ytsearch1:{q}")
            except Exception as e:
                log.warning("yt search failed for %r: %s", q, e)
                entries = []
            if entries:
                t = _to_track(entries[0], requester, video)
                if t:
                    tracks.append(t)
        if not tracks:
            raise ResolveError("spotify-no-match")
        return tracks

    if URL_RE.match(text_or_url):
        try:
            entries = await _extract(text_or_url, limit=20)
        except Exception as e:
            raise ResolveError(f"extract-failed: {e}")
        for e in entries:
            t = _to_track(e, requester, video)
            if t:
                tracks.append(t)
    else:
        try:
            entries = await _extract(f"ytsearch1:{text_or_url}")
        except Exception as e:
            raise ResolveError(f"search-failed: {e}")
        if entries:
            t = _to_track(entries[0], requester, video)
            if t:
                tracks.append(t)

    if not tracks:
        raise ResolveError("not-found")
    return tracks


def _download_sync(track: Track, video: bool) -> str | None:
    opts = _base_opts()
    opts.update(
        {
            "outtmpl": os.path.join(DOWNLOADS_DIR, "%(id)s.%(ext)s"),
            "overwrites": True,
        }
    )
    if video:
        opts.update(
            {
                "format": "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]",
                "merge_output_format": "mp4",
            }
        )
    else:
        opts.update({"format": "bestaudio/best"})

    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(track.url, download=True)
        except Exception as e:
            log.warning("download failed for %s: %s", track.url, e)
            return None
        if not info:
            return None
        path = ydl.prepare_filename(info)
        if path and os.path.exists(path):
            return path
        # Fallback: locate by id (extension may differ after merge).
        base = os.path.join(DOWNLOADS_DIR, str(info.get("id")))
        for ext in (".webm", ".m4a", ".mp4", ".opus", ".mp3", ".mkv"):
            if os.path.exists(base + ext):
                return base + ext
    return None


async def download(track: Track, video: bool = False) -> str | None:
    """Download a track to disk and return the local path (or None)."""
    if track.file_path and os.path.exists(track.file_path):
        return track.file_path
    path = await asyncio.to_thread(_download_sync, track, video)
    if path:
        track.file_path = path
    return path
