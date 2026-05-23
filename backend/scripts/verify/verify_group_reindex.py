import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.ingestion.search_indexer import index_groups_from_db
from app.core.search import get_opensearch_client
from app.db.session import SessionLocal


def verify():
    print("Starting group re-indexing...")
    try:
        count = index_groups_from_db(job_id=None)
        print(f"Successfully indexed {count} groups.")

        print("Querying OpenSearch to verify 'id' field...")
        client = get_opensearch_client()
        query = {"size": 1, "query": {"match_all": {}}}
        resp = client.search(index="groups", body=query)
        hits = resp.get("hits", {}).get("hits", [])
        if hits:
            source = hits[0].get("_source", {})
            print(f"Found group in OpenSearch: {source}")
            if "id" in source:
                print(f"VERIFICATION SUCCESS: 'id' field is present: {source['id']}")
            else:
                print(
                    "VERIFICATION FAILURE: 'id' field is missing from document source."
                )
        else:
            print("No groups found in OpenSearch to verify.")

    except Exception as e:
        print(f"Error during verification: {e}")


if __name__ == "__main__":
    verify()
