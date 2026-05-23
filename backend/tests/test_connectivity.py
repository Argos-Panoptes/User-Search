import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

print("Starting connectivity test...", flush=True)

try:
    from app.db.session import SessionLocal
    from sqlalchemy import text

    print("Imported SessionLocal.", flush=True)
    db = SessionLocal()
    print("Created Session.", flush=True)
    result = db.execute(text("SELECT 1"))
    print(f"DB Connection Successful: {result.scalar()}", flush=True)
    db.close()
except Exception as e:
    print(f"DB Connection Failed: {e}", flush=True)

try:
    from app.core.search import get_opensearch_client

    print("Imported get_opensearch_client.", flush=True)
    client = get_opensearch_client()
    print("Created OpenSearch client.", flush=True)
    info = client.info()
    print(f"OpenSearch Connection Successful: {info['version']['number']}", flush=True)
except Exception as e:
    import traceback

    traceback.print_exc()
    print(f"OpenSearch Connection Failed: {e}", flush=True)
