
import sys
import os

print("Script starting...", flush=True)

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

print("Imports starting...", flush=True)
try:
    from app.core.search import get_opensearch_client
    from app.ingestion.search_indexer import index_users_from_db, index_groups_from_db, INDEX_USERS, INDEX_GROUPS
    from app.core.logging import logger
    print("Imports success.", flush=True)
except Exception as e:
    print(f"Import failed: {e}", flush=True)
    sys.exit(1)

def reindex_all():
    client = get_opensearch_client()
    
    force = len(sys.argv) > 1 and sys.argv[1] == "--force"

    if not force:
        print("WARNING: This will DELETE all existing 'users' and 'groups' indices in OpenSearch.")
        confirm = input("Type 'yes' to proceed: ")
        if confirm != "yes":
            print("Aborted.")
            return
    else:
        print("Force mode enabled. Proceeding without confirmation.", flush=True)

    # 1. Delete Indices
    if client.indices.exists(index=INDEX_USERS):
        print(f"Deleting index: {INDEX_USERS}", flush=True)
        client.indices.delete(index=INDEX_USERS)
    
    if client.indices.exists(index=INDEX_GROUPS):
        print(f"Deleting index: {INDEX_GROUPS}", flush=True)
        client.indices.delete(index=INDEX_GROUPS)

    print("Indices deleted. Starting re-indexing...", flush=True)

    # 2. Re-index Users
    print("Indexing Users...", flush=True)
    user_count = index_users_from_db(job_id=None, log_func=print)
    print(f"Indexed {user_count} users.", flush=True)

    # 3. Re-index Groups
    print("Indexing Groups...", flush=True)
    group_count = index_groups_from_db(job_id=None, log_func=print)
    print(f"Indexed {group_count} groups.", flush=True)

    print("\nRe-indexing Complete!", flush=True)
    print(f"Total Users: {user_count}", flush=True)
    print(f"Total Groups: {group_count}", flush=True)

if __name__ == "__main__":
    reindex_all()
