import sys
import os

# Set up path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from app.db.session import SessionLocal
    from app.db.schemas.ingestion_models import IngestionJob

    print("Connecting to DB...", flush=True)
    db = SessionLocal()
    print("Querying jobs...", flush=True)
    jobs = (
        db.query(IngestionJob)
        .filter(IngestionJob.ingestion_type == "link_reconstruction")
        .all()
    )
    print(f"Found {len(jobs)} link_reconstruction jobs", flush=True)
    for j in jobs:
        print(f"ID: {j.id}, Status: {j.status}, Created: {j.created_at}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
