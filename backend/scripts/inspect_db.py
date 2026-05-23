import sys
import os
from sqlalchemy import create_engine, text

# Add the project root to sys.path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.config import settings


def inspect_constraints():
    engine = create_engine(settings.DATABASE_URL)
    tables = ["group_memberships_map", "user_timeline_ledger", "group_timeline_ledger"]

    with engine.connect() as conn:
        for table in tables:
            print(f"\n--- Constraints for {table} ---")
            query = text(
                """
                SELECT
                    conname as constraint_name,
                    pg_get_constraintdef(c.oid) as constraint_definition
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = :table
            """
            )
            results = conn.execute(query, {"table": table}).fetchall()
            for row in results:
                print(f"Constraint: {row.constraint_name}")
                print(f"Definition: {row.constraint_definition}")

            print(f"\n--- Indices for {table} ---")
            query = text(
                """
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = :table
            """
            )
            results = conn.execute(query, {"table": table}).fetchall()
            for row in results:
                print(f"Index: {row.indexname}")
                print(f"Definition: {row.indexdef}")


if __name__ == "__main__":
    inspect_constraints()
