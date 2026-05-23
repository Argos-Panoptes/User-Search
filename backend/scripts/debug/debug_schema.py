import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

from sqlalchemy import create_engine, inspect
from app.core.config import settings


def check_schema():
    print(f"Connecting to {settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)

    table = "user_metadata"
    if not inspector.has_table(table):
        print(f"Table {table} not found!")
        return

    pk = inspector.get_pk_constraint(table)
    print(f"PK: {pk}")

    unique = inspector.get_unique_constraints(table)
    print(f"Unique Constraints: {unique}")

    indexes = inspector.get_indexes(table)
    print(f"Indexes: {indexes}")


if __name__ == "__main__":
    check_schema()
