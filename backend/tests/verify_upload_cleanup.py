import os
import shutil
import time
import uuid
from app.controllers.upload_controller import UploadController


def test_cleanup():
    print("Starting verification of UploadController cleanup logic...")

    # Get the actual upload directory
    upload_dir = UploadController.UPLOAD_DIR
    print(f"Target directory: {upload_dir}")

    # Ensure directory exists
    os.makedirs(upload_dir, exist_ok=True)

    # 1. Test cleanup_stale_uploads
    print("\nTesting cleanup_stale_uploads...")

    # Create an 'old' folder (older than 24h)
    old_upload_id = str(uuid.uuid4())
    old_path = os.path.join(upload_dir, old_upload_id)
    os.makedirs(old_path, exist_ok=True)
    # Set mtime to 25 hours ago
    past_time = time.time() - (25 * 3600)
    os.utime(old_path, (past_time, past_time))
    print(f"Created stale folder: {old_upload_id}")

    # Create a 'new' folder
    new_upload_id = str(uuid.uuid4())
    new_path = os.path.join(upload_dir, new_upload_id)
    os.makedirs(new_path, exist_ok=True)
    print(f"Created fresh folder: {new_upload_id}")

    # Run cleanup
    removed = UploadController.cleanup_stale_uploads(max_age_hours=24)
    print(f"Cleanup removed {removed} folders.")

    # Verify
    old_exists = os.path.exists(old_path)
    new_exists = os.path.exists(new_path)

    print(f"Stale folder still exists? {old_exists} (Expected: False)")
    print(f"Fresh folder still exists? {new_exists} (Expected: True)")

    if not old_exists and new_exists:
        print("SUCCESS: cleanup_stale_uploads works as expected.")
    else:
        print("FAILURE: cleanup_stale_uploads failed verification.")
        return False

    # 2. Test abort_upload
    print("\nTesting abort_upload...")
    abort_upload_id = str(uuid.uuid4())
    abort_path = os.path.join(upload_dir, abort_upload_id)
    os.makedirs(abort_path, exist_ok=True)
    print(f"Created folder for abort: {abort_upload_id}")

    UploadController.abort_upload(abort_upload_id)

    abort_exists = os.path.exists(abort_path)
    print(f"Aborted folder still exists? {abort_exists} (Expected: False)")

    if not abort_exists:
        print("SUCCESS: abort_upload works as expected.")
    else:
        print("FAILURE: abort_upload failed verification.")
        return False

    # Cleanup fresh folder created for test
    if os.path.exists(new_path):
        shutil.rmtree(new_path)

    return True


if __name__ == "__main__":
    try:
        if test_cleanup():
            print("\nALL VERIFICATIONS PASSED")
            exit(0)
        else:
            print("\nVERIFICATION FAILED")
            exit(1)
    except Exception as e:
        print(f"\nERROR DURING VERIFICATION: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
