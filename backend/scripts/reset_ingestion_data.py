"""
Reset all ingestion data so you can re-ingest fresh files.
Clears: DB tables, OpenSearch indices, and uploaded files.
Does NOT touch: auth accounts, sessions, system settings.

Usage:
    python scripts/reset_ingestion_data.py
"""

import shutil
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import requests

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/user_search")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
EXPORT_DATA_DIR = Path(os.getenv("EXPORT_DATA_DIR", "export_data"))

TABLES = [
    "group_memberships_map",
    "group_membership_history",
    "user_timeline_ledger",
    "group_timeline_ledger",
    "user_history",
    "group_history",
    "avatar_history",
    "avatars",
    "user_metadata",
    "groups",
    "ingestion_logs",
    "ingestion_substeps",
    "ingestion_steps",
    "ingestion_jobs",
]

INDICES = ["users", "groups"]


def reset_db():
    print("\n--- Truncating database tables ---")
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in TABLES:
            try:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                print(f"  Truncated: {table}")
            except Exception as e:
                print(f"  Skip {table}: {e}")
    engine.dispose()


def reset_opensearch():
    print("\n--- Deleting OpenSearch indices ---")
    for index in INDICES:
        try:
            resp = requests.delete(f"{OPENSEARCH_URL}/{index}", timeout=5)
            if resp.status_code == 200:
                print(f"  Deleted index: {index}")
            else:
                print(f"  Skip {index}: {resp.text}")
        except Exception as e:
            print(f"  Skip {index}: {e}")


def reset_uploads():
    print("\n--- Clearing upload files ---")
    for folder in ["uploads", "temp_uploads"]:
        target = EXPORT_DATA_DIR / folder
        if target.exists():
            count = sum(1 for _ in target.iterdir())
            shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)
            print(f"  Cleared: {target} ({count} items)")
        else:
            print(f"  Skip: {target} (not found)")


if __name__ == "__main__":
    print("=== Resetting Ingestion Data ===")
    reset_db()
    reset_opensearch()
    reset_uploads()
    print("\nDone! Ready for fresh ingestion.")
