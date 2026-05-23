from app.db.session import engine
from sqlalchemy import text


def check_sessions():
    with engine.connect() as connection:
        result = connection.execute(
            text('SELECT id, token, "expiresAt", "userId" FROM session LIMIT 5')
        )
        rows = result.fetchall()
        if not rows:
            print("No sessions found in database.")
        else:
            print(f"Found {len(rows)} sessions:")
            for row in rows:
                print(
                    f"ID: {row[0]}, Token (start): {str(row[1])[:10]}..., Expires: {row[2]}, UserID: {row[3]}"
                )


if __name__ == "__main__":
    check_sessions()
