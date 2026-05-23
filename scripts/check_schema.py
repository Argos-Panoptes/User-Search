import sys
import os
import logging
from sqlalchemy import create_engine, inspect

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append(backend_path)

from app.core.config import settings

def check_schema():
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    columns = inspector.get_columns("user_metadata")
    for col in columns:
        if col["name"] == "export_timestamp":
            logger.info(f"Column: {col['name']}")
            logger.info(f"Type: {col['type']}")
            logger.info(f"Full Description: {col}")
            return
    logger.error("Column export_timestamp not found!")

if __name__ == "__main__":
    check_schema()
