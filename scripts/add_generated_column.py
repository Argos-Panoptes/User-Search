import sys
import os
import logging
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append(backend_path)

from app.core.config import settings

def add_generated_column():
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.begin() as conn:
        logger.info("Adding generated column 'export_timestamp_epoch' to user_metadata...")
        try:
            # 1. Drop the column if it exists (to fix cases where it was created as a plain column)
            conn.execute(text("ALTER TABLE user_metadata DROP COLUMN IF EXISTS export_timestamp_epoch;"))
            
            # 2. Re-create it as a GENERATED column
            # Note: We use ::BIGINT explicitly to match the model
            sql = """
            ALTER TABLE user_metadata 
            ADD COLUMN export_timestamp_epoch BIGINT 
            GENERATED ALWAYS AS (EXTRACT(EPOCH FROM export_timestamp)::BIGINT) STORED;
            """
            conn.execute(text(sql))
            logger.info("Successfully added 'export_timestamp_epoch' column (Generated).")
        except Exception as e:
            logger.error(f"Failed to add generated column: {e}")
            raise e

if __name__ == "__main__":
    add_generated_column()
