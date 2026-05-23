import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.core.config import settings
from app.controllers.user_controller import UserController
from app.db.schemas.ingestion_models import (
    UserMetadata,
    UserTimelineLedger,
    UserHistory,
    GroupMembershipHistory,
    GroupMetadata,
)

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_ledger_logic():
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    test_service_id = "TEST_LEDGER_USER"
    test_group_id = "TEST_GROUP_1"

    try:
        logger.info("Setting up test data...")
        # Clean previous
        db.execute(
            text(
                "DELETE FROM group_membership_history WHERE user_id IN (SELECT id FROM user_metadata WHERE service_id = :sid)"
            ),
            {"sid": test_service_id},
        )
        db.execute(
            text("DELETE FROM user_history WHERE service_id = :sid"),
            {"sid": test_service_id},
        )
        db.execute(
            text("DELETE FROM user_timeline_ledger WHERE service_id = :sid"),
            {"sid": test_service_id},
        )
        db.execute(
            text(
                "DELETE FROM group_memberships_map WHERE user_id IN (SELECT id FROM user_metadata WHERE service_id = :sid)"
            ),
            {"sid": test_service_id},
        )
        db.execute(
            text("DELETE FROM user_metadata WHERE service_id = :sid"),
            {"sid": test_service_id},
        )
        db.execute(
            text("DELETE FROM groups WHERE group_id = :gid"), {"gid": test_group_id}
        )
        db.commit()

        # Create User
        user = UserMetadata(
            service_id=test_service_id,
            name="Test User",
            export_timestamp=datetime.now(timezone.utc),
        )
        db.add(user)

        # Create Group
        group = GroupMetadata(group_id=test_group_id, group_name="Test Group 777")
        db.add(group)
        db.commit()
        db.refresh(user)
        db.refresh(group)

        # ---------------------------------------------------------
        # Scenario 1: Profile Change (Job 1)
        # ---------------------------------------------------------
        logger.info("Simulating Job 1 (Profile Change)...")
        ts1 = datetime.now(timezone.utc) - timedelta(hours=2)
        job1_id = 101

        # Create Ledger
        ledger1 = UserTimelineLedger(
            user_id=user.id,
            service_id=test_service_id,
            job_id=job1_id,
            export_timestamp=ts1,
            has_profile_change=True,
            has_membership_change=False,
        )
        db.add(ledger1)
        db.commit()  # Get ID

        # Create History Linked
        hist1 = UserHistory(
            service_id=test_service_id,
            name="Test User V1",
            snapshot_hash=b"hash1",
            history_operation="INSERT",
            history_date=ts1,
            export_timestamp=ts1,
            last_updated_job_id=job1_id,
            timeline_id=ledger1.id,
        )
        db.add(hist1)
        db.commit()

        # ---------------------------------------------------------
        # Scenario 2: Membership Change (Job 2)
        # ---------------------------------------------------------
        logger.info("Simulating Job 2 (Membership Change)...")
        ts2 = datetime.now(timezone.utc) - timedelta(hours=1)
        job2_id = 102

        # Create Ledger
        ledger2 = UserTimelineLedger(
            user_id=user.id,
            service_id=test_service_id,
            job_id=job2_id,
            export_timestamp=ts2,
            has_profile_change=False,
            has_membership_change=True,
        )
        db.add(ledger2)
        db.commit()

        # Create Membership History Linked
        mem1 = GroupMembershipHistory(
            user_id=user.id,
            group_id=group.id,
            role="member",
            valid_from=ts2,
            valid_to=None,
            job_id=job2_id,
            timeline_id=None,  # My processor logic didn't mandate valid_to has timeline_id, but inserts DO.
            # Wait, inserts DO have timeline_id in my processor logic.
        )
        # Processor inserts with timeline_id for NEW memberships.
        # But wait, GroupMembershipHistory model Step 202 has timeline_id.
        mem1.timeline_id = (
            None  # Simulating the start record? NO, start record has timeline_id.
        )
        # Update: In my Processor logic, I set timeline_id on INSERT.
        mem1.timeline_id = ledger2.id

        db.add(mem1)
        db.commit()

        # ---------------------------------------------------------
        # Verify API
        # ---------------------------------------------------------
        logger.info("Verifying API Output...")
        history = UserController.get_user_history(db, test_service_id)

        logger.info(f"Received {len(history)} history entries.")
        for h in history:
            logger.info(
                f" - ID: {h['historyId']}, Date: {h['historyDate']}, Ops: {h.get('operation')}, Changes: {h.get('changes')}"
            )
            if h.get("currentData", {}).get("groupMemberships"):
                logger.info(f"   Memberships: {h['currentData']['groupMemberships']}")

        # Assertions
        assert len(history) == 2, f"Expected 2 entries, got {len(history)}"

        # Newest first (Job 2)
        entry2 = history[0]
        assert entry2["historyId"] == ledger2.id
        assert "membership" in entry2["changes"]
        assert "profile" not in entry2["changes"]
        # Check if profile data was carried over from Job 1
        assert entry2["currentData"]["name"] == "Test User V1"
        # Check memberships
        assert (
            entry2["currentData"]["groupMemberships"][0]["groupName"]
            == "Test Group 777"
        )

        # Oldest (Job 1)
        entry1 = history[1]
        assert entry1["historyId"] == ledger1.id
        assert "profile" in entry1["changes"]
        assert "membership" not in entry1["changes"]
        assert entry1["currentData"]["name"] == "Test User V1"
        assert len(entry1["currentData"]["groupMemberships"]) == 0  # No memberships yet

        logger.info("VERIFICATION SUCCESSFUL: Unified Ledger Logic Works!")

    except Exception as e:
        logger.error(f"Verification Failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    verify_ledger_logic()
