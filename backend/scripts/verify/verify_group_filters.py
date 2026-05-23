import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from fastapi.testclient import TestClient
from app.main import app
from app.api import deps
from sqlalchemy.orm import Session


def get_test_db():
    try:
        db = deps.SessionLocal()
        yield db
    finally:
        db.close()


# Override dependency if needed, but TestClient usually works with main app if DB is accessible
# app.dependency_overrides[deps.get_db] = get_test_db

client = TestClient(app)


def test_group_filters():
    print("--- Testing Group Filters ---")

    # 1. Test max_members
    print("\n1. Testing max_members=10...")
    response = client.get(
        "/api/v1/groups/search", params={"max_members": 10, "limit": 20}
    )
    if response.status_code != 200:
        print(f"FAILED: {response.text}")
        return

    results = response.json()
    print(f"Fetched {len(results)} groups.")

    max_fail = False
    for g in results:
        if g["numberOfMembers"] > 10:
            print(
                f"FAILURE: Group {g['groupId']} has {g['numberOfMembers']} members (expected <= 10)"
            )
            max_fail = True
    if not max_fail:
        print("SUCCESS: max_members filter working.")

    # 2. Test has_link=True
    print("\n2. Testing has_link=True...")
    response = client.get(
        "/api/v1/groups/search", params={"has_link": True, "limit": 20}
    )
    if response.status_code != 200:
        print(f"FAILED: {response.text}")
        return

    results = response.json()
    print(f"Fetched {len(results)} groups.")

    link_fail = False
    for g in results:
        if not g.get("groupLink"):
            print(f"FAILURE: Group {g['groupId']} has no link (expected link)")
            link_fail = True

    if not link_fail and len(results) > 0:
        print("SUCCESS: has_link=True filter working.")
    elif len(results) == 0:
        print("WARNING: No groups found with links, cannot verify positive case.")

    # 3. Test has_link=False
    print("\n3. Testing has_link=False...")
    response = client.get(
        "/api/v1/groups/search", params={"has_link": False, "limit": 20}
    )
    if response.status_code != 200:
        print(f"FAILED: {response.text}")
        return

    results = response.json()
    print(f"Fetched {len(results)} groups.")

    no_link_fail = False
    for g in results:
        if g.get("groupLink"):
            print(
                f"FAILURE: Group {g['groupId']} has link {g['groupLink']} (expected None)"
            )
            no_link_fail = True

    if not no_link_fail:
        print("SUCCESS: has_link=False filter working.")


if __name__ == "__main__":
    test_group_filters()
