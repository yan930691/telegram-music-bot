import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "music_bot")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Channel ID for new release notifications (e.g. "@your_channel" or "-1001234567890")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

# Optional: enables Shazam-style song recognition (voice / video note)
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN", "")

# Optional: restrict web search/external download to only these user IDs (empty = everyone)
ALLOWED_USERS = [int(x.strip()) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip()]

MUSIC_DIR = os.path.join(os.path.dirname(__file__), "data", "music")
os.makedirs(MUSIC_DIR, exist_ok=True)

CHUNK_SIZE = 1024 * 512  # 512KB chunks for downloading

# Build marker so you can verify which version is running on Render
BUILD_VERSION = os.getenv("BUILD_VERSION", "v0.7.0")
