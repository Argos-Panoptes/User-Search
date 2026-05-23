import sys
import os
import time

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Local override for verification script outside Docker
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/user_search"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from app.controllers.jobs_controller import JobsController
from app.db.schemas.ingestion_models import IngestionJob

def log(msg):
    with open("rollback_log.txt", "a") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

def verify_rollback():
    # Clear previous log
    if os.path.exists("rollback_log.txt"):
        os.remove("rollback_log.txt")
        
    log("Starting Rollback Verification...")
    
    db = SessionLocal()
    try:
        # 1. Setup Data - Job 1 (Base State)
        job1 = JobsController.create_job(db, "users")
        job1.status = "completed"
        db.commit()
        log(f"Created Base Job ID: {job1.id}")

        # Insert User A (Base Version)
        db.execute(text("""
            INSERT INTO user_metadata (service_id, name, last_updated_job_id)
            VALUES ('1001', 'User A Base', :job_id)
            ON CONFLICT (service_id) DO UPDATE SET name = 'User A Base', last_updated_job_id = :job_id
        """), {"job_id": job1.id})
        db.commit()
        log("Inserted User A (Base Version)")

        # 2. Setup Data - Job 2 (Target for Rollback)
        job2 = JobsController.create_job(db, "users")
        job2.status = "completed"
        db.commit()
        log(f"Created Target Job ID: {job2.id}")

        # Update User A -> Modified
        db.execute(text("""
            UPDATE user_metadata 
            SET name = 'User A Modified', last_updated_job_id = :job_id 
            WHERE service_id = '1001'
        """), {"job_id": job2.id})

        # Insert User B (New User)
        db.execute(text("""
            INSERT INTO user_metadata (service_id, name, last_updated_job_id)
            VALUES ('1002', 'User B New', :job_id)
        """), {"job_id": job2.id})
        db.commit()
        log("Updated User A and Inserted User B (Target Version)")

        # Verify Job 2 State
        user_a = db.execute(text("SELECT name FROM user_metadata WHERE service_id = '1001'")).scalar()
        user_b = db.execute(text("SELECT name FROM user_metadata WHERE service_id = '1002'")).scalar()
        log(f"State Before Rollback: User A='{user_a}', User B='{user_b}'")
        
        if user_a != 'User A Modified' or user_b != 'User B New':
            log("Setup failed!")
            return

        # 3. Perform Rollback
        log(f"Rolling back Job {job2.id}...")
        
        # Identify affected (just to verify the function works)
        affected = JobsController.get_job_affected_ids(db, job2.id)
        log(f"Affected Records: {affected}")

        # Execute DB Rollback
        JobsController.perform_db_rollback(db, job2.id)
        
        # 4. Verify Post-Rollback State
        user_a_post = db.execute(text("SELECT name, last_updated_job_id FROM user_metadata WHERE service_id = '1001'")).fetchone()
        user_b_post = db.execute(text("SELECT name FROM user_metadata WHERE service_id = '1002'")).scalar()
        
        log(f"State After Rollback: User A='{user_a_post.name}', JobID={user_a_post.last_updated_job_id}, User B='{user_b_post}'")

        success = True
        if user_a_post.name != 'User A Base':
            log(f"FAILURE: User A should be 'User A Base', got '{user_a_post.name}'")
            success = False
        
        if user_a_post.last_updated_job_id != job1.id:
             log(f"FAILURE: User A Job ID should be {job1.id}, got {user_a_post.last_updated_job_id}")
             success = False

        if user_b_post is not None:
            log(f"FAILURE: User B should be deleted (None), got '{user_b_post}'")
            success = False

        if success:
            log("SUCCESS: DB Rollback verified correctly!")
        else:
            log("VERIFICATION FAILED")

    except Exception as e:
        log(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_rollback()
