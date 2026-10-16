import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "music_bot")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Channel ID for new release notifications (e.g. "@your_channel" or "-1001234567890")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

MUSIC_DIR = os.path.join(os.path.dirname(__file__), "data", "music")
os.makedirs(MUSIC_DIR, exist_ok=True)

CHUNK_SIZE = 1024 * 512  # 512KB chunks for downloading

# Build marker so you can verify which version is running on Render
BUILD_VERSION = os.getenv("BUILD_VERSION", "v0.9.1")

# ======================= Voice Chat (VC) streaming =======================
# Owner/assistant credentials from https://my.telegram.org/apps
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")

# Pyrogram StringSession of a *user* account ("assistant") that joins the
# group voice chat and streams the audio. Bots (Bot API) cannot stream VC.
# Generate one locally with:  python generate_session.py
SESSION = os.getenv("SESSION", "")

# Streaming limits / toggles
DURATION_LIMIT = int(os.getenv("DURATION_LIMIT", "60")) * 60  # minutes -> seconds
QUEUE_LIMIT = int(os.getenv("QUEUE_LIMIT", "20"))
VIDEO_PLAY = os.getenv("VIDEO_PLAY", "True").lower() == "true"

# Where downloaded media is stored before/while streaming
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "data", "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Optional: Netscape cookies.txt path (helps YouTube avoid "confirm you're not a bot")
COOKIES_FILE = os.getenv("COOKIES_FILE", "")

# Optional: Spotify Web API client credentials (best Spotify support). Without
# these the bot still resolves Spotify links via the public oEmbed endpoint.
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

# Helper: are the streaming features configured and usable?
STREAM_ENABLED = bool(API_ID and API_HASH and SESSION)
