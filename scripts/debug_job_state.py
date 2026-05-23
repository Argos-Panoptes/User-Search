
import sys
import os
from sqlalchemy import text, create_engine
import json

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.config import settings

def debug_job_state(job_id=None):
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        print(f"\n--- Debugging Job State (Target Job ID: {job_id}) ---")
        
        # 1. Check User Metadata distribution of job_ids
        print("\n1. user_metadata - last_updated_job_id distribution:")
        sql = "SELECT last_updated_job_id, COUNT(*) FROM user_metadata GROUP BY last_updated_job_id"
        rows = conn.execute(text(sql)).fetchall()
        for r in rows:
            print(f"   Job ID: {r[0]} -> Count: {r[1]}")
            
        # 2. Check User History distribution
        print("\n2. user_history - last_updated_job_id distribution:")
        sql = "SELECT last_updated_job_id, history_operation, COUNT(*) FROM user_history GROUP BY last_updated_job_id, history_operation"
        rows = conn.execute(text(sql)).fetchall()
        for r in rows:
            print(f"   Job ID: {r[0]} | Op: {r[1]} -> Count: {r[2]}")
            
        if job_id:
            print(f"\n3. Specific Check for Job {job_id}:")
            # count in main
            c_main = conn.execute(text(f"SELECT COUNT(*) FROM user_metadata WHERE last_updated_job_id = {job_id}")).scalar()
            print(f"   main table records: {c_main}")
            
            # count in history
            c_hist = conn.execute(text(f"SELECT COUNT(*) FROM user_history WHERE last_updated_job_id = {job_id}")).scalar()
            print(f"   history table records: {c_hist}")

            
            # Check if any history exists at all for this job
            if c_hist == 0:
                print("   [!] NO HISTORY records found for this job. Rollback will do nothing.")
            elif c_main == 0 and c_hist > 0:
                 # Check history operations
                 ops = conn.execute(text(f"SELECT DISTINCT history_operation FROM user_history WHERE last_updated_job_id = {job_id}")).fetchall()
                 print(f"   History contains operations: {[o[0] for o in ops]}")
                 if 'INSERT' in [o[0] for o in ops]:
                     print("   [!] Main table has 0 records but History has INSERTs. This suggests they were already deleted (Rollback might have worked?).")
                 
if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_job_state(sys.argv[1])
    else:
        debug_job_state()
