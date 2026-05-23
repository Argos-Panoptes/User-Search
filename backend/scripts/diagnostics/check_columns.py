from sqlalchemy import create_engine, text
from app.core.config import settings

def check_columns():
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM user_metadata LIMIT 1"))
            keys = result.keys()
            print(f"Columns in user_metadata: {list(keys)}")
            
            row = result.fetchone()
            if row:
                print(f"Sample row: {dict(zip(keys, row))}")
                
            result_g = conn.execute(text("SELECT * FROM groups LIMIT 1"))
            keys_g = result_g.keys()
            print(f"Columns in groups: {list(keys_g)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_columns()
