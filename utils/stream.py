"""Voice-chat streaming manager.

Streaming a Telegram group voice chat requires an MTProto *user* client (the
"assistant") because the Bot API cannot join calls.  We therefore run a
Pyrogram (kurigram) Client logging in with a StringSession in the same asyncio
loop as the aiogram bot, and drive it with PyTgCalls.

aiogram is used only for messages/commands; the assistant performs playback.
"""

import asyncio
import logging
from collections import defaultdict, deque

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SESSION, API_ID, API_HASH, DURATION_LIMIT, QUEUE_LIMIT
from utils import formatters as fmt
from utils.ytdl import Track, download

log = logging.getLogger("stream")

try:
    from pyrogram import Client
    from pyrogram.enums import ChatMemberStatus
    from pyrogram.errors import ChatAdminRequired, UserNotParticipant
    from pytgcalls import PyTgCalls, types as ptg_types
    import pytgcalls.exceptions as ptg_exceptions

    _AVAILABLE = True
except Exception as _imp_err:  # pragma: no cover - depends on install
    _AVAILABLE = False
    _IMPORT_ERROR = _imp_err


class StreamError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def vc_controls_kb(chat_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⏸ ရပ်", callback_data="vc:pause")
    b.button(text="▶️ ပြန်", callback_data="vc:resume")
    b.button(text="⏭ ကျော်", callback_data="vc:skip")
    b.button(text="⏹ ရပ်/ရှင်း", callback_data="vc:stop")
    b.adjust(2, 2)
    return b.as_markup()


class StreamManager:
    def __init__(self):
        self.client = None
        self.calls = None
        self.bot = None
        self.ready = False
        self.queues: dict[int, deque] = defaultdict(deque)
        self.loops: dict[int, int] = defaultdict(int)
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    # ------------------------------ lifecycle ------------------------------
    async def boot(self, bot) -> None:
        self.bot = bot
        if not _AVAILABLE:
            raise StreamError(f"libs-missing: {_IMPORT_ERROR}")
        if not SESSION:
            raise StreamError("no-session")

        self.client = Client(
            name="music_assistant",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION,
            in_memory=True,
        )
        await self.client.start()
        me = await self.client.get_me()
        log.info("Assistant started: %s (id=%s)", me.first_name, me.id)

        self.calls = PyTgCalls(self.client, cache_duration=100)
        await self.calls.start()
        self._register_handlers()
        self.ready = True
        log.info("PyTgCalls streaming ready.")

    async def close(self) -> None:
        try:
            if self.client:
                await self.client.stop()
        except Exception:
            pass

    def _register_handlers(self) -> None:
        @self.calls.on_update()
        async def _on_update(_, update):
            try:
                if isinstance(update, ptg_types.StreamEnded):
                    if update.stream_type == ptg_types.StreamEnded.Type.AUDIO:
                        await self.play_next(update.chat_id)
                elif isinstance(update, ptg_types.ChatUpdate):
                    if update.status in (
                        ptg_types.ChatUpdate.Status.KICKED,
                        ptg_types.ChatUpdate.Status.LEFT_GROUP,
                        ptg_types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                    ):
                        await self.stop(update.chat_id, notify=False)
            except Exception:
                log.exception("stream update handler failed")

    # ------------------------------- state ---------------------------------
    def active(self, chat_id: int) -> bool:
        return bool(self.queues.get(chat_id))

    def get_current(self, chat_id: int) -> Track | None:
        q = self.queues.get(chat_id)
        return q[0] if q else None

    def get_queue(self, chat_id: int) -> list[Track]:
        return list(self.queues.get(chat_id) or [])

    def set_loop(self, chat_id: int, count: int) -> None:
        self.loops[chat_id] = max(0, count)

    def get_loop(self, chat_id: int) -> int:
        return self.loops.get(chat_id, 0)

    # ------------------------------ assistant ------------------------------
    async def ensure_assistant(self, chat_id: int) -> bool:
        """Make sure the assistant user account is a member of the chat."""
        try:
            me = await self.client.get_me()
        except Exception:
            return True
        try:
            member = await self.client.get_chat_member(chat_id, me.id)
            if member.status not in (
                ChatMemberStatus.BANNED,
                ChatMemberStatus.RESTRICTED,
            ):
                return True
        except UserNotParticipant:
            pass
        except ChatAdminRequired:
            return True
        except Exception:
            return True
        # Assistant is not a member yet -> join using a bot-created invite link.
        try:
            chat = await self.bot.get_chat(chat_id)
            link = chat.invite_link
            if not link:
                link = await self.bot.export_chat_invite_link(chat_id)
            await self.client.join_chat(link)
            await asyncio.sleep(1)
            return True
        except Exception as e:
            log.warning("assistant could not join %s: %s", chat_id, e)
            return False

    # ------------------------------ playback -------------------------------
    def enqueue(self, chat_id: int, track: Track) -> int:
        self.queues[chat_id].append(track)
        return len(self.queues[chat_id]) - 1

    async def begin(self, chat_id: int, track: Track) -> None:
        """Start playing now (queue is expected to be empty)."""
        self.queues[chat_id].clear()
        self.queues[chat_id].append(track)
        await self._play_current(chat_id)

    async def _play_current(self, chat_id: int, seek: int = 0) -> None:
        track = self.get_current(chat_id)
        if track is None:
            raise StreamError("no-track")
        if track.duration_sec and track.duration_sec > DURATION_LIMIT:
            raise StreamError("duration-limit")
        if not track.file_path:
            path = await download(track, video=track.video)
            if not path:
                raise StreamError("download-failed")
            track.file_path = path

        stream = ptg_types.MediaStream(
            media_path=track.file_path,
            audio_parameters=ptg_types.AudioQuality.HIGH,
            video_parameters=ptg_types.VideoQuality.HD_720p,
            audio_flags=ptg_types.MediaStream.Flags.REQUIRED,
            video_flags=(
                ptg_types.MediaStream.Flags.AUTO_DETECT
                if track.video
                else ptg_types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=f"-ss {seek}" if seek > 1 else None,
        )
        try:
            await self.calls.play(
                chat_id=chat_id,
                stream=stream,
                config=ptg_types.GroupCallConfig(auto_start=False),
            )
        except ptg_exceptions.NoActiveGroupCall:
            raise StreamError("no-active-call")
        except Exception as e:
            log.warning("play failed in %s: %s", chat_id, e)
            raise StreamError("play-failed")

    async def play_next(self, chat_id: int, notify: bool = True) -> None:
        async with self._locks[chat_id]:
            if not self.queues.get(chat_id):
                await self.stop(chat_id, notify=False)
                return
            if self.loops.get(chat_id, 0) > 0:
                self.loops[chat_id] -= 1
                try:
                    await self._play_current(chat_id)
                except StreamError as e:
                    log.warning("loop replay failed: %s", e.code)
                await self._notify(chat_id, fmt.vc_replaying())
                return
            self.queues[chat_id].popleft()
            if not self.queues[chat_id]:
                await self.stop(chat_id, notify=False)
                await self._notify(chat_id, fmt.vc_queue_empty())
                return
            try:
                await self._play_current(chat_id)
            except StreamError as e:
                log.warning("next play failed: %s", e.code)
            if notify:
                await self._notify_now_playing(chat_id)

    async def pause(self, chat_id: int) -> bool:
        try:
            await self.calls.pause(chat_id)
            return True
        except Exception:
            return False

    async def resume(self, chat_id: int) -> bool:
        try:
            await self.calls.resume(chat_id)
            return True
        except Exception:
            return False

    async def seek(self, chat_id: int, seconds: int) -> None:
        await self._play_current(chat_id, seek=seconds)

    async def stop(self, chat_id: int, notify: bool = False) -> None:
        self.queues.pop(chat_id, None)
        self.loops.pop(chat_id, None)
        try:
            await self.calls.leave_call(chat_id, close=False)
        except Exception:
            pass
        if notify:
            await self._notify(chat_id, fmt.vc_stopped())

    # ------------------------------ messaging ------------------------------
    async def _notify(self, chat_id: int, text: str) -> None:
        try:
            await self.bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception:
            pass

    async def _notify_now_playing(self, chat_id: int) -> None:
        track = self.get_current(chat_id)
        if not track:
            return
        try:
            await self.bot.send_message(
                chat_id,
                fmt.vc_now_playing(track.title, track.duration, track.requester),
                parse_mode="HTML",
                reply_markup=vc_controls_kb(chat_id),
            )
        except Exception:
            pass


stream = StreamManager()
