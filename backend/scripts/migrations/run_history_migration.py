import sys
from sqlalchemy import create_engine, text


def run_migration():
    # Use the expected local URL
    db_url = "postgresql://postgres:postgres@localhost:5432/user_search"
    engine = create_engine(db_url)
    sql_file = r"d:\auto-backup\colin\projects\user-search\user-search-code-here\backend\scripts\migrate_history_columns.sql"

    try:
        with open(sql_file, "r") as f:
            sql = f.read()

        print(f"Connecting to {db_url}...")
        with engine.begin() as conn:
            print("Executing SQL...")
            conn.execute(text(sql))
            print("Commit successful.")

        print("MIGRATION SUCCESSFUL: History tables now have mirrored columns.")
    except Exception as e:
        print(f"MIGRATION FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
