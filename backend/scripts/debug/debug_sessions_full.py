from sqlalchemy import text
from app.db.session import engine
import os


def debug_sessions():
    # Force use of localhost to match Auth server if possible
    # but let's stick to what backend uses first
    print(f"DATABASE_URL used by backend: {engine.url}")

    with engine.connect() as connection:
        try:
            result = connection.execute(
                text('SELECT id, token, "expiresAt", "userId" FROM "session" LIMIT 5')
            )
            rows = result.fetchall()
            if not rows:
                print("No sessions found in 'session' table.")
                # Check if table exists with different case or prefix
                return

            print(f"Found {len(rows)} sessions:")
            for row in rows:
                token = str(row[1])
                print(f"ID: {row[0]}")
                print(f"Token Length: {len(token)}")
                print(f"Token (start): {token[:16]}...")
                print(f"Expires: {row[2]}")
                print("-" * 20)
        except Exception as e:
            print(f"Error querying sessions: {e}")


if __name__ == "__main__":
    debug_sessions()
