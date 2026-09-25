import logging
import os
import re
import tempfile

from mutagen import File as MutagenFile

MAX_READ_SIZE = 80 * 1024 * 1024  # skip files larger than 80 MB

_AUDIO_EXTS = (".mp3", ".m4a", ".ogg", ".wav", ".opus", ".flac", ".aac", ".opus")

_TRACK_RE = re.compile(r"^\s*\[?\s*(\d{1,3})\s*\]?\s*(?=[^0-9A-Za-z]|$)")


def extract_track_no(text: str):
    """Return the leading track number ("01 - Song", "1. Song", "[03] A") or None."""
    t = (text or "").strip()
    if not t:
        return None
    m = _TRACK_RE.match(t)
    if not m or not m.group(1):
        return None
    return int(m.group(1))


def pick_song_title(file_name: str, id3_title: str = "") -> str:
    """Prefer the real PC file name over junk embedded titles.

    Many MP3s carry generic tags such as "Unknown track" / "VA - Unknown
    track".  Admins who rename files before uploading expect the bot to use
    their filename instead.  Falls back to the embedded title when there is
    no usable filename.
    """
    name = (file_name or "").strip()
    if name:
        low = name.lower()
        for ext in _AUDIO_EXTS:
            if low.endswith(ext):
                name = name[: -len(ext)].strip()
                low = name.lower()
                break
        if _looks_generic(low):
            name = ""
    if name:
        return name or (id3_title or "").strip()
    return (id3_title or "").strip()


def _looks_generic(low: str) -> bool:
    generic = {
        "unknown",
        "unknown track",
        "unknown title",
        "unknown artist",
        "untitled",
        "track",
        "va",
        "va-unknown track",
        "various artists",
        "",
    }
    if low in generic:
        return True
    if low.startswith(("audio_", "voice ")):
        return True
    return False


async def read_audio_metadata(bot, file_id: str, file_size: int = 0):
    """Download the audio file and read embedded metadata tags.

    Returns a dict with keys: title, artist, album, track (empty strings when
    the file has no tags or reading fails).
    """
    if file_size > MAX_READ_SIZE:
        return {}
    try:
        file = await bot.get_file(file_id)
        if file.file_size and file.file_size > MAX_READ_SIZE:
            return {}
        dest = tempfile.mktemp(prefix="sng_", suffix=".bin")
        await bot.download_file(file.file_path, destination=dest)
        try:
            return await _read_tags(dest)
        finally:
            try:
                os.remove(dest)
            except OSError:
                pass
    except RuntimeError:
        return {}
    except Exception as e:
        logging.warning(f"ID3 read failed for {file_id}: {e}")
        return {}


async def _read_tags(path: str):
    import asyncio

    return await asyncio.to_thread(_read_tags_sync, path)


def _read_tags_sync(path: str):
    result = {"title": "", "artist": "", "album": "", "track": ""}
    try:
        audio = MutagenFile(path)
        if audio is None or audio.tags is None:
            return result
        tags = audio.tags

        def first(*keys):
            for k in keys:
                if hasattr(tags, "getall"):
                    frames = tags.getall(k)
                    for f in frames:
                        val = str(f).strip()
                        if val and val != "0":
                            return val
                elif k in tags:
                    val = str(tags[k]).strip()
                    if val and val not in ("0", "[]", "['']", "['0']"):
                        return val
            return ""

        result["title"] = first("TIT2", "Title", "\xa9nam")
        result["artist"] = first("TPE1", "Artist", "\xa9ART", "artist")
        result["album"] = first("TALB", "Album", "\xa9alb", "album")
        result["track"] = first("TRCK", "tracknumber")
    except Exception as e:
        logging.warning(f"ID3 tag parse failed: {e}")
    return result