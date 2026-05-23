from sqlalchemy import text
from app.db.session import engine
import os


def debug_sessions():
    output = []
    output.append(f"DATABASE_URL used by backend: {engine.url}")

    # Try connecting
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text('SELECT id, token, "expiresAt", "userId" FROM "session" LIMIT 5')
            )
            rows = result.fetchall()
            if not rows:
                output.append("No sessions found in 'session' table.")
            else:
                output.append(f"Found {len(rows)} sessions:")
                for row in rows:
                    token = str(row[1])
                    output.append(f"ID: {row[0]}")
                    output.append(f"Token Length: {len(token)}")
                    output.append(f"Token (start): {token[:16]}...")
                    output.append(f"Expires: {row[2]}")
                    output.append("-" * 20)
    except Exception as e:
        output.append(f"Error querying sessions: {e}")

    with open("session_debug_output.txt", "w") as f:
        f.write("\n".join(output))


if __name__ == "__main__":
    debug_sessions()
