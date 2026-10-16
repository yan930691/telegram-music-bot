from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGODB_URI, DB_NAME

DEFAULT_CATEGORIES = [
    "မြန်မာသီချင်း",
    "အင်္ဂလိပ်သီချင်း",
    "အသံဇာတ်လမ်း",
    "ဓမ္မတရားတော်များ",
    "စာပေစကားပြောပွဲ",
    "အခြား",
]

# Albums saved without an explicit category (channel auto-save, forwards) live
# here so they are never invisible in the category browser.
AUTO_CATEGORY = "အလိုအလျောက်"


class Database:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        self.client = AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DB_NAME]
        # Ensure indexes
        await self.db.albums.create_index("name")
        await self.db.songs.create_index("album_id")
        await self.db.songs.create_index("title")
        await self.db.songs.create_index("artist_id")
        await self.db.artists.create_index("name")

    async def close(self):
        if self.client:
            self.client.close()

    # ---------------- Categories ----------------
    async def get_categories(self):
        return await self.db.categories.find().to_list(length=100)

    async def seed_default_categories(self):
        added = []
        for name in DEFAULT_CATEGORIES:
            existing = await self.db.categories.find_one({"name": name})
            if not existing:
                await self.db.categories.insert_one({"name": name, "description": ""})
                added.append(name)
        return added

    async def get_category(self, cat_id):
        return await self.db.categories.find_one({"_id": cat_id})

    async def get_or_create_category(self, name, description=""):
        name = (name or "").strip()
        if not name:
            return None
        cat = await self.db.categories.find_one({"name": name})
        if cat:
            return cat
        res = await self.db.categories.insert_one(
            {"name": name, "description": description}
        )
        return await self.db.categories.find_one({"_id": res.inserted_id})

    async def backfill_album_categories(self, category_id, valid_category_ids=None):
        """Reassign every album that has no category (or points at a deleted one)
        so it always shows up in the category browser. Returns how many moved."""
        if valid_category_ids:
            query = {"category_id": {"$nin": list(valid_category_ids)}}
        else:
            query = {"category_id": None}
        res = await self.db.albums.update_many(
            query,
            {"$set": {"category_id": category_id}},
        )
        return res.modified_count

    async def add_category(self, name, description=""):
        return await self.db.categories.insert_one(
            {"name": name, "description": description}
        )

    async def update_category(self, cat_id, **kwargs):
        await self.db.categories.update_one({"_id": cat_id}, {"$set": kwargs})

    async def delete_category(self, cat_id):
        await self.db.categories.delete_one({"_id": cat_id})

    # ---------------- Artists ----------------
    async def get_or_create_artist(self, name):
        name = (name or "").strip()
        if not name:
            name = "အမည်မသိ"
        artist = await self.db.artists.find_one({"name": name})
        if artist:
            return artist
        res = await self.db.artists.insert_one(
            {"name": name, "created_at": __import__("datetime").datetime.utcnow()}
        )
        return await self.db.artists.find_one({"_id": res.inserted_id})

    async def get_all_artists(self, limit=100):
        return await self.db.artists.find().sort("name", 1).to_list(length=limit)

    async def get_artist(self, artist_id):
        return await self.db.artists.find_one({"_id": artist_id})

    async def search_artists(self, query, limit=10):
        regex = {"$regex": query, "$options": "i"}
        return await self.db.artists.find({"name": regex}).to_list(length=limit)

    async def get_artist_albums(self, artist_id, limit=100):
        return await self.db.albums.find({"artist_id": artist_id}).to_list(length=limit)

    async def count_artist_songs(self, artist_id):
        return await self.db.songs.count_documents({"artist_id": artist_id})

    # ---------------- Albums ----------------
    async def get_albums(self, cat_id=None):
        query = {"category_id": cat_id} if cat_id else {}
        return await self.db.albums.find(query).to_list(length=100)

    async def get_all_albums(self, limit=200):
        return await self.db.albums.find().sort("name", 1).to_list(length=limit)

    async def get_album(self, album_id):
        return await self.db.albums.find_one({"_id": album_id})

    async def add_album(self, name, artist="", category_id=None, cover="", artist_id=None):
        return await self.db.albums.insert_one(
            {
                "name": name,
                "artist": artist,
                "artist_id": artist_id,
                "category_id": category_id,
                "cover": cover,
                "downloads": 0,
                "created_at": __import__("datetime").datetime.utcnow(),
            }
        )

    async def get_or_create_album(self, name, artist="", category_id=None, cover="", artist_id=None, move_category=False):
        # Prefer an album with the same name inside the requested category.
        if category_id is not None:
            album = await self.db.albums.find_one(
                {"name": name, "category_id": category_id}
            )
            if album:
                return await self._fill_album(album, artist, category_id, artist_id)
        album = None
        if artist_id:
            album = await self.db.albums.find_one({"name": name, "artist_id": artist_id})
        if album is None:
            album = await self.db.albums.find_one({"name": name})
        if album is not None:
            return await self._fill_album(album, artist, category_id, artist_id, move_category)
        res = await self.add_album(name, artist, category_id, cover, artist_id)
        return await self.db.albums.find_one({"_id": res.inserted_id})

    async def _fill_album(self, album, artist="", category_id=None, artist_id=None, move_category=False):
        """Top up missing fields on an existing album. If the album had no
        category it is adopted into the chosen one; with ``move_category`` an
        explicitly chosen category wins (so uploads always land where the admin
        expects instead of being silently reused under an old category)."""
        updates = {}
        if artist_id and (not album.get("artist_id") or not album.get("artist")):
            updates["artist_id"] = artist_id
            updates["artist"] = artist or album.get("artist", "")
        elif artist and not album.get("artist"):
            updates["artist"] = artist
        if category_id is not None and (not album.get("category_id") or move_category):
            updates["category_id"] = category_id
        if updates:
            await self.db.albums.update_one({"_id": album["_id"]}, {"$set": updates})
            album.update(updates)
        return album

    async def update_album(self, album_id, **kwargs):
        await self.db.albums.update_one({"_id": album_id}, {"$set": kwargs})

    async def delete_album(self, album_id):
        await self.db.albums.delete_one({"_id": album_id})
        await self.db.songs.delete_many({"album_id": album_id})

    async def delete_artist_if_empty(self, artist_id):
        remaining_albums = await self.db.albums.count_documents({"artist_id": artist_id})
        remaining_songs = await self.db.songs.count_documents({"artist_id": artist_id})
        if remaining_albums == 0 and remaining_songs == 0:
            await self.db.artists.delete_one({"_id": artist_id})

    async def increment_album_downloads(self, album_id):
        await self.db.albums.update_one({"_id": album_id}, {"$inc": {"downloads": 1}})

    # ---------------- Songs ----------------
    async def get_songs(self, album_id):
        songs = await self.db.songs.find({"album_id": album_id}).to_list(length=100)
        # Natural order is unreliable; keep the album in the admin's track order.
        # Numbered tracks sort first (by their number), then unnumbered by upload time.
        songs.sort(
            key=lambda s: (
                s.get("track_no") is None,
                s.get("track_no") or 0,
                s.get("created_at"),
            )
        )
        return songs

    async def get_all_songs(self, limit=200):
        return await self.db.songs.find().sort("title", 1).to_list(length=limit)

    async def get_song(self, song_id):
        return await self.db.songs.find_one({"_id": song_id})

    async def add_song(self, title, album_id, file_id, file_size=0, duration=0, artist_id=None, track_no=None):
        return await self.db.songs.insert_one(
            {
                "title": title,
                "album_id": album_id,
                "artist_id": artist_id,
                "file_id": file_id,
                "file_size": file_size,
                "duration": duration,
                "track_no": track_no,
                "downloads": 0,
                "created_at": __import__("datetime").datetime.utcnow(),
            }
        )

    async def update_song(self, song_id, **kwargs):
        await self.db.songs.update_one({"_id": song_id}, {"$set": kwargs})

    async def get_latest_songs(self, limit=10):
        return (
            await self.db.songs.find()
            .sort("created_at", -1)
            .limit(limit)
            .to_list(length=limit)
        )

    async def delete_song(self, song_id):
        song = await self.db.songs.find_one({"_id": song_id})
        await self.db.songs.delete_one({"_id": song_id})
        if song and song.get("artist_id"):
            await self.delete_artist_if_empty(song["artist_id"])

    async def increment_song_downloads(self, song_id):
        await self.db.songs.update_one({"_id": song_id}, {"$inc": {"downloads": 1}})

    # ---------------- Search ----------------
    async def search_songs(self, query):
        # Case-insensitive regex search
        regex = {"$regex": query, "$options": "i"}
        return await self.db.songs.find({"$or": [{"title": regex}]}).to_list(length=20)

    # ---------------- Users ----------------
    async def add_user(self, user_id, username, first_name):
        existing = await self.db.users.find_one({"_id": user_id})
        if not existing:
            await self.db.users.insert_one(
                {
                    "_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "total_downloads": 0,
                    "created_at": __import__("datetime").datetime.utcnow(),
                }
            )
            return True
        return False

    async def get_user(self, user_id):
        return await self.db.users.find_one({"_id": user_id})

    async def increment_user_downloads(self, user_id):
        await self.db.users.update_one({"_id": user_id}, {"$inc": {"total_downloads": 1}})

    async def get_stats(self):
        songs = await self.db.songs.count_documents({})
        albums = await self.db.albums.count_documents({})
        users = await self.db.users.count_documents({})
        return {"songs": songs, "albums": albums, "users": users}

    # ---------------- Pending upload batches (survive bot restarts) ----------------
    async def get_pending_upload(self, user_id):
        return await self.db.pending_uploads.find_one({"_id": user_id})

    async def save_pending_upload(self, user_id, **fields):
        await self.db.pending_uploads.update_one(
            {"_id": user_id},
            {"$set": fields},
            upsert=True,
        )

    async def append_pending_song(self, user_id, song):
        await self.db.pending_uploads.update_one(
            {"_id": user_id},
            {"$push": {"pending_songs": song}},
            upsert=True,
        )

    async def clear_pending_upload(self, user_id):
        await self.db.pending_uploads.delete_one({"_id": user_id})


db = Database()
