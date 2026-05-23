import sys
import os
import sqlalchemy
from sqlalchemy import create_engine, text

# Add backend directory to sys.path
backend_path = os.path.join(os.getcwd(), 'backend')
sys.path.append(backend_path)
print(f"Added {backend_path} to sys.path", file=sys.stdout)

try:
    from app.core.config import settings
    print(f"Imported settings. DATABASE_URL: {settings.DATABASE_URL}", file=sys.stdout)
except ImportError as e:
    print(f"Failed to import settings: {e}", file=sys.stdout)
    # Fallback for testing
    settings = None

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/user_search"
print(f"Using DATABASE_URL: {DATABASE_URL}", file=sys.stdout)

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print(f"Connection successful: {result.scalar()}", file=sys.stdout)
except Exception as e:
    print(f"Connection failed: {e}", file=sys.stdout)
