import logging
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.core.config import settings
from app.controllers.user_controller import UserController
from app.db.session import SessionLocal


# Setup Logger
# Setup Logger
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)
# Bypass logger for debug
class Logger:
    def info(self, msg):
        print(f"[INFO] {msg}")
        sys.stdout.flush()


logger = Logger()


def setup_test_data(db):
    logger.info("Setting up test data...")
    # 1. Clean previous
    db.execute(text("DELETE FROM user_history WHERE service_id = 'TEST_UNIFIED'"))
    db.execute(
        text(
            "DELETE FROM group_membership_history WHERE user_id = (SELECT id FROM user_metadata WHERE service_id = 'TEST_UNIFIED')"
        )
    )
    db.execute(
        text(
            "DELETE FROM group_memberships_map WHERE user_id = (SELECT id FROM user_metadata WHERE service_id = 'TEST_UNIFIED')"
        )
    )
    db.execute(text("DELETE FROM user_metadata WHERE service_id = 'TEST_UNIFIED'"))
    db.execute(text("DELETE FROM groups WHERE group_id = 'TEST_GRP_UNI'"))
    db.commit()

    # 2. Create User and Group
    db.execute(
        text(
            "INSERT INTO groups (group_id, group_name) VALUES ('TEST_GRP_UNI', 'Unified Group')"
        )
    )
    db.execute(
        text(
            "INSERT INTO user_metadata (service_id, name, export_timestamp) VALUES ('TEST_UNIFIED', 'InitName', NOW())"
        )
    )
    db.commit()

    user_id = db.execute(
        text("SELECT id FROM user_metadata WHERE service_id = 'TEST_UNIFIED'")
    ).scalar()
    group_id = db.execute(
        text("SELECT id FROM groups WHERE group_id = 'TEST_GRP_UNI'")
    ).scalar()

    return user_id, group_id


def insert_profile_history(db, user_id, name, date_offset_minutes):
    logger.info(f"Inserting Profile History at T-{date_offset_minutes}m")
    sql = text(
        f"""
        INSERT INTO user_history (
            service_id, history_operation, history_date, 
            name, profile_name, last_updated_job_id, export_timestamp
        ) VALUES (
            'TEST_UNIFIED', 'UPDATE', NOW() - INTERVAL '{date_offset_minutes} minutes',
            :name, :name, 1, NOW() - INTERVAL '{date_offset_minutes} minutes'
        )
    """
    )
    db.execute(sql, {"name": name})
    db.commit()


def insert_membership_history(
    db, user_id, group_id, role, date_offset_minutes, is_active=True
):
    logger.info(f"Inserting Membership History at T-{date_offset_minutes}m ({role})")
    valid_to = "NULL" if is_active else "NOW()"

    # Simple history record insertion
    sql = text(
        f"""
        INSERT INTO group_membership_history (
            user_id, group_id, role, valid_from, valid_to, job_id
        ) VALUES (
            {user_id}, {group_id}, '{role}', 
            NOW() - INTERVAL '{date_offset_minutes} minutes', 
            {valid_to}, 
            1
        )
    """
    )
    db.execute(sql)
    db.commit()


def verify_timeline():
    db = SessionLocal()
    try:
        user_id, group_id = setup_test_data(db)

        # Timeline Construction:
        # T-40m: Profile Created (Name = "Alpha")
        insert_profile_history(db, user_id, "Alpha", 40)

        # T-30m: Join Group (Membership Change) -> SHOULD BE VISIBLE
        insert_membership_history(db, user_id, group_id, "member", 30, is_active=True)

        # T-20m: Profile Rename (Name = "Beta") -> VISIBLE (Profile)
        insert_profile_history(db, user_id, "Beta", 20)

        # T-10m: Leave Group (Membership Change) -> SHOULD BE VISIBLE
        # (Technically 'Leave' means active history ends, or a new history with valid_to?
        # Our model inserts a new record? No, leaving is usually just setting valid_to on the old one.
        # But for 'Change', we might interpret 'valid_to' update as an event?
        # Let's simulate a Role Change to 'admin' instead, simpler to model as an INSERT)
        insert_membership_history(db, user_id, group_id, "admin", 10, is_active=True)

        logger.info("Fetching History via Controller...")
        history = UserController.get_user_history(db, "TEST_UNIFIED")

        print(f"\nTotal History Entries: {len(history)}")
        for h in history:
            ts = h.get("historyDate")
            op = h.get("operation")
            name = h.get("currentData", {}).get("name")
            mems = h.get("currentData", {}).get("group_memberships", [])
            print(
                f" - {datetime.fromtimestamp(ts) if ts else 'None'} | {op} | Name: {name} | Mems: {len(mems)}"
            )

        # Verification Logic
        # We expect 4 entries if Unified.
        # We expect 2 entries if Legacy (Only Profile).

        if len(history) == 4:
            print("\n[SUCCESS] Unified History is WORKING. Found 4 entries.")
        elif len(history) == 2:
            print(
                "\n[FAIL] Unified History NOT IMPLEMENTED. Found only 2 entries (Profile only)."
            )
        else:
            print(f"\n[?] Unexpected count: {len(history)}")

    finally:
        db.close()


if __name__ == "__main__":
    verify_timeline()
