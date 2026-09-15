# Myanmar Music Library Bot

Python + Telegram Bot API + MongoDB bot.

## Features
- Album browsing
- Album cover
- Song names from audio caption/title
- Send stored Telegram audio by file_id
- Music search
- Admin album/song adding
- MongoDB storage

## Local setup

1. Copy `.env.example` to `.env`
2. Fill in:
   - BOT_TOKEN
   - MONGODB_URI
   - MONGODB_DB_NAME
   - ADMIN_IDS
3. Install:
   `pip install -r requirements.txt`
4. Run:
   `python bot.py`

## Render

Use a Background Worker and start command:

`python bot.py`

Set the environment variables in Render instead of uploading `.env`.
