import sys
import os
import json
import zlib
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta, timezone

# Force local DB
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/user_search"

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.controllers.user_controller import UserController
from app.db.session import SessionLocal


def verify_membership_history_integration():
    print("Connecting to DB...")
    engine = create_engine(settings.DATABASE_URL)
    db = SessionLocal()
    print("Connected.")

    try:
        print("1. Setup Test Data...")
        with engine.begin() as conn:
            # Clean
            conn.execute(
                text("DELETE FROM user_history WHERE service_id = 'test-hist-integ'")
            )
            conn.execute(
                text("DELETE FROM group_membership_history WHERE user_id = 99998")
            )
            conn.execute(
                text("DELETE FROM group_memberships_map WHERE user_id = 99998")
            )
            conn.execute(text("DELETE FROM groups WHERE id IN (88887, 88886)"))
            conn.execute(text("DELETE FROM user_metadata WHERE id = 99998"))

            # Insert User
            conn.execute(
                text(
                    """
                INSERT INTO user_metadata (id, service_id, profile_name, last_updated_job_id, export_timestamp)
                VALUES (99998, 'test-hist-integ', 'Integ Tester', 1, to_timestamp(2000))
            """
                )
            )

            # Insert Groups
            conn.execute(
                text(
                    "INSERT INTO groups (id, group_id, group_name) VALUES (88887, 'g887', 'Group A')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO groups (id, group_id, group_name) VALUES (88886, 'g886', 'Group B')"
                )
            )

            # Insert Membership History Spells
            # Spell 1: Group A active from T=0 to T=150
            conn.execute(
                text(
                    """
                INSERT INTO group_membership_history (user_id, group_id, role, valid_from, valid_to)
                VALUES (99998, 88887, 'member', to_timestamp(0), to_timestamp(150))
            """
                )
            )
            # Spell 2: Group B active from T=100 (overlap) to infinity
            conn.execute(
                text(
                    """
                INSERT INTO group_membership_history (user_id, group_id, role, valid_from, valid_to)
                VALUES (99998, 88886, 'admin', to_timestamp(100), NULL)
            """
                )
            )

        print("2. Create User History Snapshots...")
        # H1 at T=50 (Only Group A should be active)
        # H2 at T=120 (Both Group A and Group B should be active)
        # H3 at T=200 (Only Group B should be active)

        with engine.begin() as conn:
            blob = zlib.compress(json.dumps({"profile_name": "T50"}).encode("utf-8"))
            conn.execute(
                text(
                    """
                INSERT INTO user_history (service_id, history_operation, current_data, history_date, snapshot_hash)
                VALUES ('test-hist-integ', 'UPDATE', :blob, to_timestamp(50), 'h1')
            """
                ),
                {"blob": blob},
            )

            blob = zlib.compress(json.dumps({"profile_name": "T120"}).encode("utf-8"))
            conn.execute(
                text(
                    """
                INSERT INTO user_history (service_id, history_operation, current_data, history_date, snapshot_hash)
                VALUES ('test-hist-integ', 'UPDATE', :blob, to_timestamp(120), 'h2')
            """
                ),
                {"blob": blob},
            )

            blob = zlib.compress(json.dumps({"profile_name": "T200"}).encode("utf-8"))
            conn.execute(
                text(
                    """
                INSERT INTO user_history (service_id, history_operation, current_data, history_date, snapshot_hash)
                VALUES ('test-hist-integ', 'UPDATE', :blob, to_timestamp(200), 'h3')
            """
                ),
                {"blob": blob},
            )

        print("3. Verify Retrieval...")
        history = UserController.get_user_history(db, "test-hist-integ")
        # should be desc: [T200, T120, T50]

        print(f"Retrieved {len(history)} records.")

        # Test T200 (latest)
        h3 = history[0]
        m3 = h3["currentData"]["groupMemberships"]
        print(f"T200 Memberships: {[m['groupName'] for m in m3]}")
        assert len(m3) == 1
        assert m3[0]["groupName"] == "Group B"
        assert h3["currentData"]["adminGroups"] == ["Group B"]

        # Test T120 (middle)
        h2 = history[1]
        m2 = h2["currentData"]["groupMemberships"]
        print(f"T120 Memberships: {[m['groupName'] for m in m2]}")
        assert len(m2) == 2
        names = sorted([m["groupName"] for m in m2])
        assert names == ["Group A", "Group B"]

        # Test T50 (oldest)
        h1 = history[2]
        m1 = h1["currentData"]["groupMemberships"]
        print(f"T50 Memberships: {[m['groupName'] for m in m1]}")
        assert len(m1) == 1
        assert m1[0]["groupName"] == "Group A"

        print("SUCCESS: Membership history correctly integrated into user snapshots.")

    finally:
        # Cleanup
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM user_history WHERE service_id = 'test-hist-integ'")
            )
            conn.execute(
                text("DELETE FROM group_membership_history WHERE user_id = 99998")
            )
            conn.execute(
                text("DELETE FROM group_memberships_map WHERE user_id = 99998")
            )
            conn.execute(text("DELETE FROM groups WHERE id IN (88887, 88886)"))
            conn.execute(text("DELETE FROM user_metadata WHERE id = 99998"))
        db.close()


if __name__ == "__main__":
    try:
        verify_membership_history_integration()
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
