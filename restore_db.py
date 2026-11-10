"""Restore MongoDB data from a backup JSON.

Usage:
    python restore_db.py "<MONGODB_URI>" mongo-data-backup-2026-11-11.json [--force]

JSON ဖွဲ့စည်းပုံ: {"<db_name>": {"<collection>": [docs, ...]}}

- Document တွေကို _id အသစ်နဲ့ ထည့်ပေးမယ် (backup မှာ _id မပါ)
- Collection ထဲမှာ အရင်က data ရှိနေရင် skip မယ် -- `--force` ပေးရင် အရင်က data ကို
  ဖျက်ပြီး အသစ်ထည့်ပေးမယ်
"""

import json
import sys

from pymongo import MongoClient


def main():
    if len(sys.argv) < 3:
        print("Usage: python restore_db.py <mongo_uri> <backup.json> [--force]")
        sys.exit(2)
    uri, path = sys.argv[1], sys.argv[2]
    force = "--force" in sys.argv

    with open(path, encoding="utf-8") as f:
        backup = json.load(f)

    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    try:
        for dbname, cols in backup.items():
            db = client[dbname]
            for cname, docs in cols.items():
                if not docs:
                    print(f"{dbname}.{cname}: empty in backup, skipped")
                    continue
                existing = db[cname].count_documents({})
                if existing and not force:
                    print(f"{dbname}.{cname}: has {existing} docs, skipped (use --force to replace)")
                    continue
                if existing and force:
                    db[cname].delete_many({})
                db[cname].insert_many(docs, ordered=False)
                print(f"{dbname}.{cname}: inserted {len(docs)}")
    finally:
        client.close()
    print("DONE")


if __name__ == "__main__":
    main()
