import sys
import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Setup logging to file
log_file = "verify_history.log"
def log(msg):
    with open(log_file, "a") as f:
        f.write(msg + "\n")
    print(msg) # Still print to stdout just in case

# Clear log file
with open(log_file, "w") as f:
    f.write("Starting verification...\n")

try:
    from app.core.config import settings
    # Override for local testing if needed, but try using loaded settings first
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/user_search"
    if settings:
         # settings.DATABASE_URL might be set to 'db' host for docker, we need localhost
         pass
         
    log(f"Using DATABASE_URL: {DATABASE_URL}")
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    from app.db.triggers import init_db_triggers
    init_db_triggers(engine)
    log("Triggers initialized.")

except Exception as e:
    log(f"Setup Error: {e}")
    sys.exit(1)

def verify_history():
    log("Verifying History Tracking...")
    session = SessionLocal()
    
    try:
        # TEST USER HISTORY
        log("\n--- Testing User History ---")
        sid = "test_user_service_id_v1"
        
        # Cleanup first
        session.execute(text("DELETE FROM user_metadata WHERE service_id = :sid"), {"sid": sid})
        session.execute(text("DELETE FROM user_history WHERE service_id = :sid"), {"sid": sid})
        session.commit()

        # 1. INSERT
        log("1. Inserting User...")
        session.execute(text("""
            INSERT INTO user_metadata (service_id, name, last_updated_job_id, export_timestamp)
            VALUES (:sid, 'Test User V1', 101, NOW())
        """), {"sid": sid})
        session.commit()
        
        # Check History
        hist = session.execute(text("SELECT * FROM user_history WHERE service_id = :sid ORDER BY history_id DESC"), {"sid": sid}).fetchall()
        log(f"History records after INSERT: {len(hist)}")
        if len(hist) > 0 and hist[0].history_operation == 'INSERT':
            if hist[0].previous_data is None and hist[0].current_data is not None:
                log("PASS: Insert captured (previous_data is None, current_data present).")
            else:
                log(f"FAIL: Insert data mismatch. Prev: {hist[0].previous_data}, Curr: {hist[0].current_data}")
        else:
            log("FAIL: Insert NOT captured.")

        # 2. UPDATE
        log("2. Updating User...")
        session.execute(text("""
            UPDATE user_metadata SET name = 'Test User V2', last_updated_job_id = 102
            WHERE service_id = :sid
        """), {"sid": sid})
        session.commit()
        
        hist = session.execute(text("SELECT * FROM user_history WHERE service_id = :sid ORDER BY history_id DESC"), {"sid": sid}).fetchall()
        log(f"History records after UPDATE: {len(hist)}")
        if len(hist) > 0 and hist[0].history_operation == 'UPDATE':
             if hist[0].previous_data['name'] == 'Test User V1' and hist[0].current_data['name'] == 'Test User V2':
                 log("PASS: Update captured (prev/curr names correct).")
             else:
                 log(f"FAIL: Update data mismatch. Prev: {hist[0].previous_data.get('name')}, Curr: {hist[0].current_data.get('name')}")
        else:
             log("FAIL: Update NOT captured.")

        # 3. DELETE
        log("3. Deleting User...")
        session.execute(text("DELETE FROM user_metadata WHERE service_id = :sid"), {"sid": sid})
        session.commit()
        
        hist = session.execute(text("SELECT * FROM user_history WHERE service_id = :sid ORDER BY history_id DESC"), {"sid": sid}).fetchall()
        log(f"History records after DELETE: {len(hist)}")
        if len(hist) > 0 and hist[0].history_operation == 'DELETE':
             if hist[0].previous_data is not None and hist[0].current_data is None:
                 log("PASS: Delete captured (previous_data present, current_data is None).")
             else:
                 log(f"FAIL: Delete data mismatch. Prev: {hist[0].previous_data}, Curr: {hist[0].current_data}")
        else:
             log("FAIL: Delete NOT captured.")


        # TEST GROUP HISTORY
        log("\n--- Testing Group History ---")
        gid = "test_group_v1"
        session.execute(text("DELETE FROM groups WHERE group_id = :gid"), {"gid": gid})
        session.execute(text("DELETE FROM group_history WHERE group_id = :gid"), {"gid": gid})
        session.commit()

        # INSERT
        session.execute(text("""
            INSERT INTO groups (group_id, group_name, last_updated_job_id)
            VALUES (:gid, 'Test Group V1', 201)
        """), {"gid": gid})
        session.commit()
        hist = session.execute(text("SELECT * FROM group_history WHERE group_id = :gid ORDER BY history_id DESC"), {"gid": gid}).fetchall()
        if len(hist) > 0 and hist[0].history_operation == 'INSERT':
            if hist[0].current_data is not None:
                log("PASS: Group Insert captured.")
            else:
                log("FAIL: Group Insert current_data missing.")
        else:
            log("FAIL: Group Insert NOT captured.")
            
        # UPDATE
        session.execute(text("""
            UPDATE groups SET group_name = 'Test Group V2'
            WHERE group_id = :gid
        """), {"gid": gid})
        session.commit()
        hist = session.execute(text("SELECT * FROM group_history WHERE group_id = :gid ORDER BY history_id DESC"), {"gid": gid}).fetchall()
        if len(hist) > 0 and hist[0].history_operation == 'UPDATE':
            if hist[0].previous_data['group_name'] == 'Test Group V1':
                log("PASS: Group Update captured.")
            else:
                log("FAIL: Group Update previous_data incorrect.")
        else:
            log("FAIL: Group Update NOT captured.")

        # TEST AVATAR HISTORY
        log("\n--- Testing Avatar History ---")
        # We need to insert with ID or let auto-increment.
        # But for test, we can use service_id
        asid = "avatar_service_id_v1"
        session.execute(text("DELETE FROM avatars WHERE service_id = :sid"), {"sid": asid})
        session.execute(text("DELETE FROM avatar_history WHERE service_id = :sid"), {"sid": asid})
        session.commit()

        # INSERT
        session.execute(text("""
            INSERT INTO avatars (service_id, filename, last_updated_job_id)
            VALUES (:sid, 'avatar1.jpg', 301)
        """), {"sid": asid})
        hist = session.execute(text("SELECT * FROM avatar_history WHERE service_id = :sid ORDER BY history_id DESC"), {"sid": asid}).fetchall()
        if len(hist) > 0 and hist[0].history_operation == 'INSERT':
            if hist[0].current_data is not None:
                log("PASS: Avatar Insert captured.")
            else:
                 log("FAIL: Avatar Insert current_data missing.")
        else:
            log("FAIL: Avatar Insert NOT captured.")

        # UPDATE
        session.execute(text("""
            UPDATE avatars SET filename = 'avatar2.jpg'
            WHERE service_id = :sid
        """), {"sid": asid})
        session.commit()
        
        hist = session.execute(text("SELECT * FROM avatar_history WHERE service_id = :sid ORDER BY history_id DESC"), {"sid": asid}).fetchall()
        if len(hist) > 0 and hist[0].history_operation == 'UPDATE':
             if hist[0].previous_data['filename'] == 'avatar1.jpg':
                log("PASS: Avatar Update captured.")
             else:
                log("FAIL: Avatar Update previous_data mismatch.")
        else:
            log("FAIL: Avatar Update NOT captured.")

        # TEST METRICS CALCULATION
        log("\n--- Testing Metrics Calculation ---")
        from app.controllers.jobs_controller import JobsController
        
        # Job 101: User Insert
        m101 = JobsController.calculate_job_metrics(session, 101)
        log(f"Job 101 Metrics for User Insert: {m101}")
        if m101.get('users_inserted', 0) >= 1:
             log("PASS: Job 101 metrics show user insertion.")
        else:
             log("FAIL: Job 101 metrics missing user insertion.")

        # Job 102: User Update
        m102 = JobsController.calculate_job_metrics(session, 102)
        log(f"Job 102 Metrics for User Update: {m102}")
        if m102.get('users_updated', 0) >= 1:
             log("PASS: Job 102 metrics show user update.")
        else:
             log("FAIL: Job 102 metrics missing user update.")
             
        # Job 201: Group Insert
        m201 = JobsController.calculate_job_metrics(session, 201)
        log(f"Job 201 Metrics for Group Insert: {m201}")
        if m201.get('groups_inserted', 0) >= 1:
            log("PASS: Job 201 metrics show group insertion.")
        else:
            log("FAIL: Job 201 metrics missing group insertion.")
            
        # Job 301: Avatar Insert
        m301 = JobsController.calculate_job_metrics(session, 301)
        log(f"Job 301 Metrics for Avatar Insert: {m301}")
        if m301.get('avatars_inserted', 0) >= 1:
            log("PASS: Job 301 metrics show avatar insertion.")
        else:
            log("FAIL: Job 301 metrics missing avatar insertion.")

    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc(file=sys.stdout) # To stdout/err for now
        with open(log_file, "a") as f:
            traceback.print_exc(file=f)
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    verify_history()
