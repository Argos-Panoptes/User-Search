
import sys
import os
import json

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.db.session import SessionLocal
from sqlalchemy import text

def inspect_history():
    db = SessionLocal()
    try:
        # Fetch one history record that has previous_data
        sql = "SELECT previous_data, current_data FROM user_history WHERE previous_data IS NOT NULL LIMIT 1"
        result = db.execute(text(sql)).fetchone()
        
        if result:
            prev = result[0]
            curr = result[1]
            print("\n--- Previous Data Sample ---")
            print(json.dumps(prev, indent=2) if prev else "None")
            print("\n--- Current Data Sample ---")
            print(json.dumps(curr, indent=2) if curr else "None")
            
            # Verify critical fields presence
            if prev:
                critical_fields = ["name", "e164", "group_memberships", "service_id"]
                missing = [f for f in critical_fields if f not in prev]
                if missing:
                    print(f"\nWARNING: Missing fields in previous_data: {missing}")
                else:
                    print("\nSUCCESS: Critical fields found in previous_data.")
        else:
            print("No history records with previous_data found.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_history()
