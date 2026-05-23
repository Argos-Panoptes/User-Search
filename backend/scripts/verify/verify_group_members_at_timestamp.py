import sys
import os

sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.controllers.group_controller import GroupController
from app.db.schemas.ingestion_models import GroupTimelineLedger, GroupMetadata

db = SessionLocal()

# Find a group with a "Left" event
print("Searching for a group with membership changes...")
timeline_entries = GroupController.get_group_timeline(
    db, "SEARCH_ALL"
)  # Wait, I can't search all.

# Helper to find a group ID
ledger_entry = (
    db.query(GroupTimelineLedger)
    .filter(GroupTimelineLedger.has_membership_change == True)
    .first()
)
if not ledger_entry:
    print("No group found with membership changes.")
    sys.exit(0)

group_pk = ledger_entry.group_pk
group = db.query(GroupMetadata).filter(GroupMetadata.id == group_pk).first()
group_id = str(group.group_id)

print(f"Testing with Group ID: {group_id}")

timeline = GroupController.get_group_timeline(db, group_id)

for event in timeline:
    diff = event.get("membershipDiff")
    if diff and diff.get("left"):
        leaver = diff["left"][0]
        ts = event["exportTimestamp"]  # Should be float now
        print(
            f"Found 'Left' event at {ts} for user {leaver['name']} ({leaver.get('serviceId')})"
        )

        # Test: Fetch members at this timestamp
        members = GroupController.get_group_members_at_timestamp(db, group_id, ts)

        # Verify leaver is NOT in members
        member_ids = [m["serviceId"] for m in members]
        if leaver.get("serviceId") in member_ids:
            print(
                f"FAILURE: User {leaver['name']} found in member list at timestamp {ts}!"
            )
            print(f"Leaver Service ID: {leaver.get('serviceId')}")
            # print(f"Members found: {member_ids}")
        else:
            print(
                f"SUCCESS: User {leaver['name']} is correctly ABSENT from member list at timestamp {ts}."
            )

        # Also check just before?
        ts_before = ts - 0.1
        members_before = GroupController.get_group_members_at_timestamp(
            db, group_id, ts_before
        )
        member_ids_before = [m["serviceId"] for m in members_before]
        if leaver.get("serviceId") in member_ids_before:
            print(
                f"SUCCESS: User {leaver['name']} is PRESENT just before timestamp ({ts_before})."
            )
        else:
            print(
                f"WARNING: User {leaver['name']} is ABSENT just before timestamp ({ts_before}). Valid_from issue?"
            )

        break
