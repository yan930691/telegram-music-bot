import logging
import os
import tempfile

from mutagen import File as MutagenFile

MAX_READ_SIZE = 80 * 1024 * 1024  # skip files larger than 80 MB


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