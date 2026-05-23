import os
import psycopg2
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def migrate_ids():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in environment")
        return

    print(f"Connecting to: {db_url}")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    try:
        print("Starting ID migration to String...")

        # 1. Drop constraints
        print("Dropping foreign key constraints...")
        # Get constraint names if they differ
        cur.execute(
            """
            SELECT conname 
            FROM pg_constraint 
            WHERE conrelid = 'subscriptions'::regclass AND contype = 'f';
        """
        )
        for (conname,) in cur.fetchall():
            print(f"Dropping constraint {conname} from subscriptions")
            cur.execute(f"ALTER TABLE subscriptions DROP CONSTRAINT {conname}")

        cur.execute(
            """
            SELECT conname 
            FROM pg_constraint 
            WHERE conrelid = 'payment_transactions'::regclass AND contype = 'f';
        """
        )
        for (conname,) in cur.fetchall():
            print(f"Dropping constraint {conname} from payment_transactions")
            cur.execute(f"ALTER TABLE payment_transactions DROP CONSTRAINT {conname}")

        cur.execute(
            """
            SELECT conname 
            FROM pg_constraint 
            WHERE conrelid = 'ingestion_jobs'::regclass AND contype = 'f';
        """
        )
        for (conname,) in cur.fetchall():
            if "created_by_id" in conname or "app_users" in conname:
                print(f"Dropping constraint {conname} from ingestion_jobs")
                cur.execute(f"ALTER TABLE ingestion_jobs DROP CONSTRAINT {conname}")

        # 2. Alter column types
        print("Altering column types to VARCHAR...")
        cur.execute("ALTER TABLE app_users ALTER COLUMN id TYPE VARCHAR(255)")
        cur.execute("ALTER TABLE subscriptions ALTER COLUMN user_id TYPE VARCHAR(255)")
        cur.execute(
            "ALTER TABLE payment_transactions ALTER COLUMN user_id TYPE VARCHAR(255)"
        )
        cur.execute(
            "ALTER TABLE ingestion_jobs ALTER COLUMN created_by_id TYPE VARCHAR(255)"
        )

        # 3. Re-add constraints with ON UPDATE CASCADE
        print("Re-adding foreign key constraints with ON UPDATE CASCADE...")
        cur.execute(
            """
            ALTER TABLE subscriptions 
            ADD CONSTRAINT subscriptions_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES app_users(id) 
            ON UPDATE CASCADE ON DELETE CASCADE
        """
        )
        cur.execute(
            """
            ALTER TABLE payment_transactions 
            ADD CONSTRAINT payment_transactions_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES app_users(id) 
            ON UPDATE CASCADE ON DELETE CASCADE
        """
        )
        cur.execute(
            """
            ALTER TABLE ingestion_jobs 
            ADD CONSTRAINT ingestion_jobs_created_by_id_fkey 
            FOREIGN KEY (created_by_id) REFERENCES app_users(id) 
            ON UPDATE CASCADE ON DELETE SET NULL
        """
        )

        conn.commit()
        print("Migration successful!")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise e
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    migrate_ids()
