import sys
import os

sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.controllers.group_controller import GroupController
from app.db.schemas.ingestion_models import GroupTimelineLedger, GroupMetadata

db = SessionLocal()

# Find a group with membership changes
print("Searching for a group with membership changes...")
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

if not group:
    print(f"Group metadata not found for PK {group_pk}")
    sys.exit(1)

group_id = str(group.group_id)  # Use the string group_id
print(f"Testing with Group ID: {group_id} (PK: {group_pk})")

timeline = GroupController.get_group_timeline(db, group_id)

found_diff = False
for event in timeline:
    if event["hasMembershipChange"]:
        diff = event.get("membershipDiff")
        if diff:
            print(f"Event {event['timelineId']}: Membership Change Detected")
            print(f"  Joined: {len(diff['joined'])}")
            print(f"  Left: {len(diff['left'])}")
            print(f"  Role Changed: {len(diff['roleChanged'])}")

            # Print samples
            if diff["joined"]:
                print(f"    Sample Join: {diff['joined'][0]['name']}")
            if diff["left"]:
                print(f"    Sample Left: {diff['left'][0]['name']}")
            if diff["roleChanged"]:
                print(
                    f"    Sample Role Change: {diff['roleChanged'][0]['name']} ({diff['roleChanged'][0]['fromRole']} -> {diff['roleChanged'][0]['toRole']})"
                )

            if (
                len(diff["joined"]) > 0
                or len(diff["left"]) > 0
                or len(diff["roleChanged"]) > 0
            ):
                found_diff = True
        else:
            print(
                f"FAILURE: Event {event['timelineId']} marked as change but missing membershipDiff!"
            )

if found_diff:
    print("\nVerification SUCCESS: Found and verified membership diffs.")
else:
    print(
        "\nVerification WARNING: Structure present but no actual users found in diffs (could be data issue)."
    )
