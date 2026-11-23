import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne


class BlogState:
    """တင်ပြီးသား Post link တွေကို MongoDB မှာ မှတ်ထားတယ် (restart-safe)"""

    def __init__(self):
        self._client = AsyncIOMotorClient(os.environ["MONGODB_URI"])
        self._col = self._client.get_database()["blog_seen_posts"]

    async def load_all(self) -> set[str]:
        return {doc["link"] async for doc in self._col.find({}, {"link": 1})}

    async def mark(self, link: str) -> None:
        await self._col.update_one(
            {"link": link}, {"$set": {"link": link}}, upsert=True
        )

    async def mark_many(self, links: list[str]) -> None:
        if not links:
            return
        ops = [UpdateOne({"link": l}, {"$set": {"link": l}}, upsert=True) for l in links]
        await self._col.bulk_write(ops, ordered=False)

    async def has(self, link: str) -> bool:
        return await self._col.count_documents({"link": link}, limit=1) > 0

    async def close(self):
        self._client.close()
