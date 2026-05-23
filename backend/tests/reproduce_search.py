import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from app.db.session import SessionLocal
from app.controllers.user_controller import UserController
from app.core.search import get_opensearch_client


def test_search():
    db = SessionLocal()
    client = get_opensearch_client()

    print("--- Testing Connection ---")
    try:
        info = client.info()
        print(f"OpenSearch Connected: {info['version']['number']}")
    except Exception as e:
        print(f"OpenSearch Connection Failed: {e}")
        return

    print("\n--- Testing Search: Service ID ---")
    # Try to find a user in DB to use as test case
    from app.db.schemas.ingestion_models import UserMetadata

    user = db.query(UserMetadata).first()

    if not user:
        print("No users found in DB to test with.")
        return

    print(f"Testing with User: {user.name} (Service ID: {user.service_id})")

    # 1. Exact Service ID Search (simulating frontend filter)
    print(f"\n1. Search by exact service_id='{user.service_id}'")
    results = UserController.search_users(db, service_id=user.service_id)
    print(f"Found {len(results)} results")
    if results:
        print(f"Top result: {results[0]['serviceId']}")

    # 2. General Query Search (simulating frontend search box)
    print(f"\n2. Search by q='{user.service_id}'")
    results = UserController.search_users(db, q=user.service_id)
    print(f"Found {len(results)} results")

    # 3. Partial Name Search
    if user.name:
        partial_name = user.name[:3]
        print(f"\n3. Search by q='{partial_name}' (Partial Name)")
        results = UserController.search_users(db, q=partial_name)
        print(f"Found {len(results)} results")

    # 4. Partial Service ID Search
    # 4. Partial Service ID Search
    if user.service_id:
        partial_sid = user.service_id[:8]
        print(f"\n4. Search by q='{partial_sid}' (Partial Service ID)")
        results = UserController.search_users(db, q=partial_sid)
        print(f"Found {len(results)} results")

    # 5. Username Wildcard Search
    if user.username:
        print(f"\n5. Search by username='{user.username}'")
        results = UserController.search_users(db, username=user.username)
        print(f"Found {len(results)} results")

    # Group Search Test
    from app.controllers.group_controller import GroupController
    from app.db.schemas.ingestion_models import GroupMetadata

    group = db.query(GroupMetadata).first()
    if group:
        print(f"\n--- Testing Group Search ---")
        print(f"Testing with Group: {group.group_name} (ID: {group.group_id})")

        print(f"\n6. Search by group_id='{group.group_id}'")
        results = GroupController.search_groups(db, group_id=group.group_id)
        print(f"Found {len(results)} results")

        if group.group_name:
            print(f"\n7. Search by group_name='{group.group_name}'")
            results = GroupController.search_groups(db, group_name=group.group_name)
            print(f"Found {len(results)} results")

        print(f"\n8. Search USERS by group_id='{group.group_id}' (String ID)")
        results = UserController.search_users(db, group_id=group.group_id)
        print(f"Found {len(results)} users in group")

    db.close()


if __name__ == "__main__":
    test_search()
