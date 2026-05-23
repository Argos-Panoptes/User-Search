from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.logging import logger

def init_db_triggers(engine):
    """
    Initializes database triggers and functions for history tracking.
    """
    logger.info("Dropping Legacy Database Triggers (Switching to App-Side History)...")
    
    with engine.begin() as conn:
        # Drop Triggers
        conn.execute(text("DROP TRIGGER IF EXISTS trg_user_history ON user_metadata"))
        conn.execute(text("DROP TRIGGER IF EXISTS trg_group_history ON groups"))
        conn.execute(text("DROP TRIGGER IF EXISTS trg_avatar_history ON avatars"))

        # Drop Functions
        conn.execute(text("DROP FUNCTION IF EXISTS process_user_history()"))
        conn.execute(text("DROP FUNCTION IF EXISTS process_group_history()"))
        conn.execute(text("DROP FUNCTION IF EXISTS process_avatar_history()"))

    logger.info("Legacy triggers dropped.")
