import sys
import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Redirect print to file
log_file = "verify_output_controller.txt"


def print_log(msg):
    with open(log_file, "a") as f:
        f.write(str(msg) + "\n")
    # Also print to stdout to trick checking
    # print(msg)


# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

print_log("Importing settings...")
from app.core.config import settings

print_log("Settings loaded.")

# Override DB URL for local execution if not in docker
settings.DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/user_search"
print_log(f"Using DB: {settings.DATABASE_URL}")

print_log("Importing UserController...")
from app.controllers.user_controller import UserController

print_log("Importing Models...")
from app.db.schemas.ingestion_models import (
    UserMetadata,
    UserHistory,
    GroupMembershipHistory,
    GroupMetadata,
)

print_log("Imports done. Starting verification...")


def verify_controller_output():
    print_log("Connecting to DB...")
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # 1. Find a user with history
        print_log("Finding a user with history...")
        # Join with history to find one that has entries
        user_id_with_history = db.query(UserHistory.service_id).limit(1).scalar()

        if not user_id_with_history:
            print_log("No user history found in DB to verify.")
            return

        print_log(f"Testing with Service ID: {user_id_with_history}")

        # 2. Call the controller
        history = UserController.get_user_history(db, user_id_with_history)

        print_log(f"Retrieved {len(history)} history entries.")

        if not history:
            print_log("History list is empty.")
            return

        first_entry = history[0]
        current_data = first_entry.get("currentData", {})

        # 3. Verify Fields
        print_log("\n--- Verifying Fields ---")
        keys = current_data.keys()
        print_log(f"Available keys in currentData: {list(keys)}")

        expected_keys = ["storage_id", "color", "verified", "capabilities"]
        for k in expected_keys:
            if k in keys:
                print_log(f"PASS: Found field '{k}'")
            else:
                print_log(f"WARN: Field '{k}' not found.")

        # 4. Verify Group Memberships
        print_log("\n--- Verifying Group Memberships ---")
        if "group_memberships" in current_data:
            print_log("PASS: 'group_memberships' key exists.")
            print_log(f"Value: {current_data['group_memberships']}")
            if isinstance(current_data["group_memberships"], list):
                print_log("PASS: 'group_memberships' is a list.")
            else:
                print_log(
                    f"FAIL: 'group_memberships' is {type(current_data['group_memberships'])}"
                )
        else:
            print_log("FAIL: 'group_memberships' key MISSING.")

    except Exception as e:
        print_log(f"ERROR: {e}")
        import traceback

        with open(log_file, "a") as f:
            traceback.print_exc(file=f)
    finally:
        db.close()


if __name__ == "__main__":
    # Clear log file
    with open(log_file, "w") as f:
        f.write("")
    verify_controller_output()
