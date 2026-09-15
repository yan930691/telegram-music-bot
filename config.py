import os
from dotenv import load_dotenv

load_dotenv()

def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

BOT_TOKEN = get_required_env("BOT_TOKEN")
MONGODB_URI = get_required_env("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "myanmar_music")

def get_admin_ids():
    raw_ids = os.getenv("ADMIN_IDS", "")
    if not raw_ids.strip():
        return set()
    admin_ids = set()
    for item in raw_ids.split(","):
        item = item.strip()
        if item:
            try:
                admin_ids.add(int(item))
            except ValueError:
                raise RuntimeError(f"Invalid ADMIN_IDS value: {item}")
    return admin_ids

ADMIN_IDS = get_admin_ids()
