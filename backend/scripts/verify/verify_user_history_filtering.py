import sys
import os
import json
import zlib
from sqlalchemy import create_engine, text, insert
from datetime import datetime, timezone

# Force local DB
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/user_search"

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.controllers.history_controller import HistoryController
from app.controllers.user_controller import UserController
from app.db.session import SessionLocal
from app.db.schemas.ingestion_models import UserMetadata


def verify_history_filtering():
    engine = create_engine(settings.DATABASE_URL)
    db = SessionLocal()

    try:
        print("1. Setup Test Data...")
        with engine.begin() as conn:
            # Clean
            conn.execute(
                text("DELETE FROM user_history WHERE service_id = 'test-hist-filter'")
            )
            conn.execute(
                text("DELETE FROM group_memberships_map WHERE user_id = 99999")
            )
            conn.execute(text("DELETE FROM groups WHERE id = 88888"))
            conn.execute(text("DELETE FROM user_metadata WHERE id = 99999"))

            # Insert User
            conn.execute(
                text(
                    """
                INSERT INTO user_metadata (id, service_id, profile_name, last_updated_job_id, export_timestamp)
                VALUES (99999, 'test-hist-filter', 'History Tester', 1, to_timestamp(1000))
            """
                )
            )

            # Insert Group
            conn.execute(
                text(
                    """
                INSERT INTO groups (id, group_id, group_name)
                VALUES (88888, 'g888', 'History Group')
            """
                )
            )

            # Insert Membership
            conn.execute(
                text(
                    """
                INSERT INTO group_memberships_map (user_id, group_id, role)
                VALUES (99999, 88888, 'member')
            """
                )
            )

        print("2. Run History Recording...")
        # We need a job_id for the function
        job_id = 1

        # We need to simulate that this user was updated in this job
        # The history recorder checks last_updated_job_id = job_id. We set it to 1 above.

        HistoryController.record_user_history_optimized(
            db, job_id=job_id, batch_size=100
        )

        print("3. Verify Storage...")
        # Check raw DB content
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        """
                SELECT current_data FROM user_history 
                WHERE service_id = 'test-hist-filter' 
                ORDER BY history_date DESC LIMIT 1
            """
                    )
                )
                .mappings()
                .first()
            )

            if not row:
                print("FAILURE: No history record found.")
                sys.exit(1)

            blob = row["current_data"]
            data = json.loads(zlib.decompress(blob))

            print(f"Stored Data Keys: {data.keys()}")

            if "groupMemberships" in data or "adminGroups" in data:
                print(
                    "FAILURE: groupMemberships or adminGroups found in stored history blob!"
                )
                print(f"Data: {data}")
                sys.exit(1)
            else:
                print("SUCCESS: Stored history filtered correctly.")

        print("4. Verify Retrieval (UserController)...")
        # Even if we stored it cleanly, let's verify retrieval logic also filters (in case of old data)
        # We'll artificially insert a "bad" record to test retrieval filtering

        bad_data = {"profile_name": "Bad History", "groupMemberships": ["fail"]}
        bad_blob = zlib.compress(json.dumps(bad_data).encode("utf-8"))

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO user_history (service_id, history_operation, previous_data, current_data, history_date, snapshot_hash)
                VALUES ('test-hist-filter', 'UPDATE', :blob, :blob, NOW(), 'dummyhash')
            """
                ),
                {"blob": bad_blob},
            )

        history = UserController.get_user_history(db, "test-hist-filter")
        latest = history[0]

        print(
            f"Retrieved Latest Previous Data Keys: {latest['previousData'].keys() if latest['previousData'] else None}"
        )

        if (
            "groupMemberships" in latest["currentData"]
            or "groupMemberships" in latest["previousData"]
        ):
            print(
                "FAILURE: UserController did not filter groupMemberships from response."
            )
            sys.exit(1)
        else:
            print("SUCCESS: UserController filtered correctly.")

    finally:
        # Cleanup
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM user_history WHERE service_id = 'test-hist-filter'")
            )
            conn.execute(
                text("DELETE FROM group_membership_history WHERE user_id = 99999")
            )
            conn.execute(
                text("DELETE FROM group_memberships_map WHERE user_id = 99999")
            )
            conn.execute(text("DELETE FROM groups WHERE id = 88888"))
            conn.execute(text("DELETE FROM user_metadata WHERE id = 99999"))
        db.close()


if __name__ == "__main__":
    try:
        verify_history_filtering()
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
