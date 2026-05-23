from sqlalchemy import text
from app.db.session import engine


def migrate():
    print("Running migrations...")
    with engine.connect() as connection:
        # Add columns to 'user' table
        columns_to_add = [
            ("role", "TEXT"),
            ("banned", "BOOLEAN"),
            ("banReason", "TEXT"),
            ("banExpires", "TIMESTAMP WITH TIME ZONE"),
            ("customerId", "TEXT"),
        ]

        for col_name, col_type in columns_to_add:
            try:
                print(f"Adding column {col_name} to 'user' table...")
                connection.execute(
                    text(
                        f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS "{col_name}" {col_type}'
                    )
                )
                connection.commit()
            except Exception as e:
                print(f"Error adding {col_name}: {e}")

    print("Migration completed.")


if __name__ == "__main__":
    migrate()
