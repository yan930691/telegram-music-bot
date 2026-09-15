from pymongo import MongoClient
from pymongo.errors import PyMongoError
from config import MONGODB_URI, MONGODB_DB_NAME

class Database:
    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client[MONGODB_DB_NAME]
        self.albums = self.db["albums"]
        self._create_indexes()

    def _create_indexes(self):
        self.albums.create_index("album_name")
        self.albums.create_index("artist")

    def create_album(self, album_name, artist, year, cover_file_id):
        album = {
            "album_name": album_name,
            "artist": artist,
            "year": year,
            "cover_file_id": cover_file_id,
            "songs": [],
        }
        result = self.albums.insert_one(album)
        return str(result.inserted_id)

    def get_all_albums(self):
        return list(self.albums.find(
            {},
            {"album_name": 1, "artist": 1, "year": 1, "cover_file_id": 1}
        ).sort("album_name", 1))

    def get_album(self, album_id):
        from bson import ObjectId
        try:
            return self.albums.find_one({"_id": ObjectId(album_id)})
        except Exception:
            return None

    def add_song(self, album_id, title, file_id, duration=0):
        from bson import ObjectId
        try:
            object_id = ObjectId(album_id)
        except Exception:
            return False

        song = {"title": title, "file_id": file_id, "duration": duration}
        result = self.albums.update_one(
            {"_id": object_id},
            {"$push": {"songs": song}}
        )
        return result.modified_count > 0

    def get_song(self, album_id, song_index):
        album = self.get_album(album_id)
        if not album:
            return None
        songs = album.get("songs", [])
        if song_index < 0 or song_index >= len(songs):
            return None
        return songs[song_index]

    def search_songs(self, query):
        regex = {"$regex": query, "$options": "i"}
        results = []
        albums = self.albums.find({
            "$or": [
                {"album_name": regex},
                {"artist": regex},
                {"songs.title": regex},
            ]
        })
        for album in albums:
            for index, song in enumerate(album.get("songs", [])):
                if (
                    query.lower() in song.get("title", "").lower()
                    or query.lower() in album.get("album_name", "").lower()
                    or query.lower() in album.get("artist", "").lower()
                ):
                    results.append({
                        "album_id": str(album["_id"]),
                        "album_name": album.get("album_name", ""),
                        "artist": album.get("artist", ""),
                        "song_index": index,
                        "title": song.get("title", ""),
                        "file_id": song.get("file_id", ""),
                    })
        return results

    def ping(self):
        try:
            self.client.admin.command("ping")
            return True
        except PyMongoError:
            return False

db = Database()
