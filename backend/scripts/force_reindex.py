import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from app.db.session import SessionLocal
from app.core.search import get_opensearch_client
from app.ingestion.search_indexer import index_users_from_db, INDEX_USERS


def force_reindex():
    print("--- Force Re-Index Users ---")
    client = get_opensearch_client()

    # 1. Delete existing index
    if client.indices.exists(index=INDEX_USERS):
        print(f"Deleting existing index: {INDEX_USERS}...")
        client.indices.delete(index=INDEX_USERS)
        print("Index deleted.")
    else:
        print(f"Index {INDEX_USERS} does not exist.")

    # 2. Re-create and Index (index_users_from_db handles creation)
    print("Starting full re-index from DB...")
    count = index_users_from_db(job_id=None, log_func=print)
    print(f"Re-indexing complete. Indexed {count} users.")


if __name__ == "__main__":
    force_reindex()
