import os
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne, ReturnDocument

MYANMAR_TZ = timezone(timedelta(hours=6, minutes=30))


class BlogState:
    def __init__(self):
        self._client = AsyncIOMotorClient(os.environ["MONGODB_URI"])
        self._db = self._client.get_database()
        self._col = self._db["blog_seen_posts"]
        self._daily = self._db["blog_daily"]

    # ---------- seen posts ----------
    async def load_all(self) -> set[str]:
        return {doc["link"] async for doc in self._col.find({}, {"link": 1})}

    async def mark(self, link: str) -> None:
        await self._col.update_one({"link": link}, {"$set": {"link": link}}, upsert=True)

    async def has(self, link: str) -> bool:
        return await self._col.count_documents({"link": link}, limit=1) > 0

    async def seen_count(self) -> int:
        return await self._col.count_documents({})

    # ---------- daily limit ----------
    @staticmethod
    def _today() -> str:
        return datetime.now(MYANMAR_TZ).strftime("%Y-%m-%d")

    async def get_daily_count(self) -> int:
        doc = await self._daily.find_one({"_id": self._today()})
        return doc.get("count", 0) if doc else 0

    async def increment_daily(self) -> int:
        doc = await self._daily.find_one_and_update(
            {"_id": self._today()},
            {"$inc": {"count": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc.get("count", 0) if doc else 1

    async def close(self):
        self._client.close()
