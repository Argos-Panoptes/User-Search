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

def fix_constraints():
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.begin() as conn:
        logger.info("Starting constraint fixes...")
        
        # 1. Groups Table (group_id)
        logger.info("Fixing 'groups' table constraints...")
        # Check uniqueness first (duplicate group_ids will fail constraint creation)
        # We might need to dedup first?
        # Let's try adding the Unique Constraint.
        try:
            conn.execute(text('ALTER TABLE groups ADD CONSTRAINT uq_groups_group_id UNIQUE (group_id)'))
            logger.info("Added unique constraint 'uq_groups_group_id' to groups(group_id)")
        except Exception as e:
            logger.warning(f"Could not add constraint to groups: {e}")
            logger.info("Attempting to create UNIQUE INDEX concurrently not supported in transaction, trying standard index approach...")
            
        # 2. User Metadata Table (service_id)
        logger.info("Fixing 'user_metadata' table constraints...")
        try:
            conn.execute(text('ALTER TABLE user_metadata ADD CONSTRAINT uq_user_metadata_service_id UNIQUE (service_id)'))
            logger.info("Added unique constraint 'uq_user_metadata_service_id' to user_metadata(service_id)")
        except Exception as e:
            logger.warning(f"Could not add constraint to user_metadata: {e}")

    logger.info("Constraint fix attempt complete.")

if __name__ == "__main__":
    fix_constraints()
