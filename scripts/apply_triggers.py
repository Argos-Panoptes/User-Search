
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.db.session import engine
from app.db.triggers import init_db_triggers

if __name__ == "__main__":
    print("Applying updated DB triggers...")
    try:
        init_db_triggers(engine)
        print("Triggers applied successfully.")
    except Exception as e:
        print(f"Error executing triggers: {e}")
        sys.exit(1)
