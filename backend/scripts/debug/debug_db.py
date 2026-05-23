from sqlalchemy import inspect, text
from app.db.session import engine


def debug_db():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables found: {tables}")

    if "session" in tables:
        with engine.connect() as conn:
            # Check the actual data in 'session' table
            res = conn.execute(text('SELECT count(*) FROM "session"'))
            count = res.scalar()
            print(f"Total session records: {count}")

            if count > 0:
                res = conn.execute(
                    text('SELECT id, token, "expiresAt" FROM "session" LIMIT 1')
                )
                row = res.fetchone()
                print(
                    f"Sample Session - ID: {row[0]}, Token (prefix): {str(row[1])[:10]}, Expires: {row[2]}"
                )


if __name__ == "__main__":
    debug_db()
