import sys
import os

# Force local DB for verification
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/user_search"

from sqlalchemy import create_engine, text
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.ingestion.processors.membership_processor import process_memberships_sql


def verify_timestamps():
    engine = create_engine(settings.DATABASE_URL)

    # 1. Setup Data
    user_service_id = "test-history-user-ts"
    group_id = 99998
    group_service_id = "test-group-ts-id"

    with engine.begin() as conn:
        # Clean up
        conn.execute(
            text(
                "DELETE FROM group_membership_history WHERE user_id = (SELECT id FROM user_metadata WHERE service_id = :sid)"
            ),
            {"sid": user_service_id},
        )
        conn.execute(
            text(
                "DELETE FROM group_memberships_map WHERE user_id = (SELECT id FROM user_metadata WHERE service_id = :sid)"
            ),
            {"sid": user_service_id},
        )
        conn.execute(
            text("DELETE FROM user_metadata WHERE service_id = :sid"),
            {"sid": user_service_id},
        )
        conn.execute(text("DELETE FROM groups WHERE id = :gid"), {"gid": group_id})

        # Insert Group (with group_id string)
        conn.execute(
            text(
                "INSERT INTO groups (id, group_id, group_name) VALUES (:gid, :gsid, 'Test Group TS')"
            ),
            {"gid": group_id, "gsid": group_service_id},
        )

        # Insert User (Target) with export_timestamp
        conn.execute(
            text(
                "INSERT INTO user_metadata (service_id, profile_name, export_timestamp) VALUES (:sid, 'Test User TS', NOW())"
            ),
            {"sid": user_service_id},
        )

    print("Setup complete.")

    # 2. Test Case 1: Initial Join (Timestamp A)
    # Use integer timestamp (seconds)
    ts_a = 1735725600  # 2025-01-01 10:00:00 UTC

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS test_verify"))
        conn.execute(text("DROP TABLE IF EXISTS test_verify.user_metadata"))
        conn.execute(
            text(
                """
            CREATE TABLE test_verify.user_metadata (
                "serviceId" text,
                "groupMemberships" jsonb,
                "adminGroups" jsonb,
                "exportTimestamp" bigint
            )
        """
            )
        )
        conn.execute(
            text(
                """
            INSERT INTO test_verify.user_metadata ("serviceId", "groupMemberships", "adminGroups", "exportTimestamp")
            VALUES (:sid, CAST(:groups AS jsonb), '[]'::jsonb, :ts)
        """
            ),
            {
                "sid": user_service_id,
                "groups": f'[{{"id": "{group_service_id}", "role": "member"}}]',
                "ts": ts_a,
            },
        )

    print(f"Running processing for Join at {ts_a}...")
    process_memberships_sql(job_id=101, staging_schema="test_verify", log_func=print)

    # Allow buffer flush
    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    """
            SELECT valid_from, valid_to 
            FROM group_membership_history 
            WHERE user_id = (SELECT id FROM user_metadata WHERE service_id = :sid)
            AND group_id = :gid
         """
                ),
                {"sid": user_service_id, "gid": group_id},
            )
            .mappings()
            .first()
        )

        print(f"Row 1: {row}")
        # Adjust check to match formatting. Python datetime vs DB str?
        # row['valid_from'] is datetime object usually with sqlalchemy.
        # We'll compare formatted strings.
        valid_from_str = str(row["valid_from"])
        if "2025-01-01 10:00:00" in valid_from_str and row["valid_to"] is None:
            print("SUCCESS: Join Timestamp Matches.")
        else:
            print(f"FAILURE: Join Timestamp Mismatch. Got {valid_from_str}")
            sys.exit(1)

    # 3. Test Case 2: Leave (Timestamp B)
    ts_b = 1738422000  # 2025-02-01 15:00:00 UTC
    print(f"Running processing for Leave at {ts_b}...")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE test_verify.user_metadata"))
        # Empty memberships -> Leave
        conn.execute(
            text(
                """
            INSERT INTO test_verify.user_metadata ("serviceId", "groupMemberships", "adminGroups", "exportTimestamp")
            VALUES (:sid, '[]', '[]', :ts)
        """
            ),
            {"sid": user_service_id, "ts": ts_b},
        )

    process_memberships_sql(job_id=102, staging_schema="test_verify", log_func=print)

    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    """
            SELECT valid_from, valid_to 
            FROM group_membership_history 
            WHERE user_id = (SELECT id FROM user_metadata WHERE service_id = :sid)
            AND group_id = :gid
         """
                ),
                {"sid": user_service_id, "gid": group_id},
            )
            .mappings()
            .first()
        )

        print(f"Row 2: {row}")
        valid_to_str = str(row["valid_to"])
        if "2025-02-01 15:00:00" in valid_to_str:
            print("SUCCESS: Leave Timestamp Matches.")
        else:
            print(f"FAILURE: Leave Timestamp Mismatch. Got {valid_to_str}")
            sys.exit(1)

    # Cleaning up
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA test_verify CASCADE"))
        # Clean up data
        conn.execute(
            text(
                "DELETE FROM group_membership_history WHERE user_id = (SELECT id FROM user_metadata WHERE service_id = :sid)"
            ),
            {"sid": user_service_id},
        )
        conn.execute(
            text(
                "DELETE FROM group_memberships_map WHERE user_id = (SELECT id FROM user_metadata WHERE service_id = :sid)"
            ),
            {"sid": user_service_id},
        )
        conn.execute(
            text("DELETE FROM user_metadata WHERE service_id = :sid"),
            {"sid": user_service_id},
        )
        conn.execute(text("DELETE FROM groups WHERE id = :gid"), {"gid": group_id})
        pass


if __name__ == "__main__":
    try:
        verify_timestamps()
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
