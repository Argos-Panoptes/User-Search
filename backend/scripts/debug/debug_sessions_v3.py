from sqlalchemy import text
from app.db.session import engine
import os


def debug_sessions():
    print(f"DATABASE_URL used by backend: {engine.url}")

    with engine.connect() as connection:
        try:
            # List all tables first to be sure
            result = connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
            )
            tables = [row[0] for row in result]
            print(f"Tables in public schema: {tables}")

            if "session" not in tables and '"session"' not in tables:
                print("Table 'session' not found!")
                return

            result = connection.execute(
                text('SELECT id, token, "expiresAt", "userId" FROM "session"')
            )
            rows = result.fetchall()
            if not rows:
                print("No sessions found in 'session' table.")
                return

            print(f"Found {len(rows)} sessions. Dumping tokens:")
            for row in rows:
                token = str(row[1])
                print(f"- Token (full): {token}")
                print(f"  Token Length: {len(token)}")
                print(f"  Expires: {row[2]}")
                print("-" * 20)
        except Exception as e:
            print(f"Error querying sessions: {e}")


if __name__ == "__main__":
    debug_sessions()
