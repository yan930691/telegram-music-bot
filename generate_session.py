"""Generate a Pyrogram StringSession for the VC assistant account.

Run this LOCALLY (not on Render) with a *user* Telegram account (a spare
account is recommended).  The printed string goes into the SESSION env var.

    python generate_session.py

You will be asked for API_ID / API_HASH (from https://my.telegram.org/apps),
your phone number and the login code Telegram sends you.
"""

import asyncio
import os

try:
    from pyrogram import Client
except ImportError:
    raise SystemExit(
        "pyrogram is not installed. Run: pip install kurigram"
    )


async def main():
    api_id = os.getenv("API_ID") or input("API_ID: ").strip()
    api_hash = os.getenv("API_HASH") or input("API_HASH: ").strip()

    app = Client(
        name="session_generator",
        api_id=int(api_id),
        api_hash=api_hash,
        in_memory=True,
    )
    async with app:
        me = await app.get_me()
        print("\nLogged in as:", me.first_name, f"(@{me.username})" if me.username else "")
        print("\n=================== SESSION ===================")
        print(app.export_session_string())
        print("===============================================")
        print("\nCopy the line above into the SESSION env var on Render.")


if __name__ == "__main__":
    asyncio.run(main())
