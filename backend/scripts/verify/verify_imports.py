import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    print("Importing app.api.v1.endpoints.jobs...")
    from app.api.v1.endpoints import jobs
    print("Success.")

    print("Importing app.tasks.ingestion_tasks...")
    from app.tasks import ingestion_tasks
    print("Success.")

except Exception as e:
    print(f"Import Error: {e}")
    sys.exit(1)
