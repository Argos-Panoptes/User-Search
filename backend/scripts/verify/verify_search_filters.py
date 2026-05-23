import logging
import sys
from app.db.session import SessionLocal
from app.controllers.group_controller import GroupController

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_filters():
    db = SessionLocal()
    try:
        logger.info("--- Testing Filters ---")

        # Test 1: Admin Approval = True
        logger.info("Searching with admin_approval_required=True")
        results_true = GroupController.search_groups(
            db, admin_approval_required=True, limit=5
        )
        for g in results_true:
            print(
                f"Group: {g.get('groupName')}, Approval: {g.get('adminApprovalRequired')}"
            )
            if g.get("adminApprovalRequired") is not True:
                print("FAIL: Expected True")

        # Test 2: Admin Approval = False
        logger.info("\nSearching with admin_approval_required=False")
        results_false = GroupController.search_groups(
            db, admin_approval_required=False, limit=5
        )
        for g in results_false:
            print(
                f"Group: {g.get('groupName')}, Approval: {g.get('adminApprovalRequired')}"
            )
            if g.get("adminApprovalRequired") is not False:
                print("FAIL: Expected False")

        # Test 3: Retention Period (if any data exists)
        # We'll just search and see if it runs without error, maybe filter by "1 week" if common
        logger.info("\nSearching with retention_period='1 week'")
        results_retention = GroupController.search_groups(
            db, retention_period="1 week", limit=5
        )
        print(f"Found {len(results_retention)} groups with 1 week retention")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    verify_filters()
