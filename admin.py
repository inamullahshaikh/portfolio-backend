"""CLI: upsert admin_users — usage: python admin.py <email> <password>"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from auth import hash_password  # noqa: E402

EMAIL = (sys.argv[1] if len(sys.argv) > 1 else "").lower().strip()
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else ""

if not EMAIL or not PASSWORD:
    print("usage: python admin.py <email> <password>", file=sys.stderr)
    sys.exit(1)

h = hash_password(PASSWORD)
client = MongoClient(os.environ["MONGODB_URI"])
db = client[os.environ["DB_NAME"]]
db.admin_users.replace_one(
    {"email": EMAIL},
    {"email": EMAIL, "password_hash": h},
    upsert=True,
)
client.close()
print("admin_users upserted for", EMAIL)
