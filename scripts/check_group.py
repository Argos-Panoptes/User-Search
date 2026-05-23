import sys
import os

# Add backend to path
import logging
logging.basicConfig(level=logging.INFO)

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
print(f"Adding to path: {backend_path}", flush=True)
sys.path.append(backend_path)

from app.db.session import SessionLocal, engine
from app.db.schemas.ingestion_models import GroupMetadata

def check_group(group_id_str):
    print(f"Connecting to DB...", flush=True)
    db = SessionLocal()
    try:
        print(f"Checking for group_id: '{group_id_str}'", flush=True)
        
        # Check by group_id string
        group = db.query(GroupMetadata).filter(GroupMetadata.group_id == group_id_str).first()
        if group:
            print(f"FOUND by group_id! PK: {group.id}, group_id: {group.group_id}", flush=True)
        else:
            print(f"NOT FOUND by group_id '{group_id_str}'.", flush=True)
            
            # Print first 5 groups
            print("Listing first 5 groups in DB:", flush=True)
            all_groups = db.query(GroupMetadata).limit(5).all()
            for g in all_groups:
                print(f" - PK: {g.id}, group_id: {g.group_id}", flush=True)

    except Exception as e:
        print(f"Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    target_id = "7"
    check_group(target_id)
    
    # Also check by ID directly
    db = SessionLocal()
    try:
        print(f"Checking for PK ID: {target_id}")
        g = db.query(GroupMetadata).filter(GroupMetadata.id == int(target_id)).first()
        if g:
            print(f"FOUND by PK ID: {g.id}, group_id: {g.group_id}")
        else:
            print("NOT FOUND by PK ID.")
    finally:
        db.close()
