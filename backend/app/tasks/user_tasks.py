from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.schemas.app_models import AppUser
from app.db.schemas.auth_tables import User  # Registers User model for FK
from app.db.schemas.stripe_models import Subscription  # noqa: F401
from app.core.celery_app import celery_app
from app.core.logging import logger


@celery_app.task
def update_last_login_task(user_id: int, login_timestamp: float):
    """
    Background task to update the last_login timestamp for a user.
    Strategy: First Update Wins (within 60s window).
    If a user is active multiple times in a minute:
    - 1st request updates DB.
    - Subsequent requests within 60s are skipped to save DB writes.
    - Resolution: ~1 minute.
    """
    db: Session = SessionLocal()
    try:
        user = db.query(AppUser).filter(AppUser.id == user_id).first()
        if user:
            # Debounce: if the last update was less than 60 seconds ago, skip
            # This prevents "writing many times to db"
            if user.last_login:
                # user.last_login is already timezone aware (DateTime(timezone=True))
                # ensure we compare with timezone aware current time
                last_login_utc = user.last_login.astimezone(timezone.utc)
                current_time_utc = datetime.fromtimestamp(
                    login_timestamp, tz=timezone.utc
                )

                # Check if the existing DB entry is fresher or close enough to the new timestamp
                delta = current_time_utc - last_login_utc
                if delta.total_seconds() < 60:
                    logger.info(
                        f"Skipping last_login update (debounce) for user_id={user_id}. "
                        f"Last login: {last_login_utc}, New timestamp: {current_time_utc}"
                    )
                    return

            user.last_login = datetime.fromtimestamp(login_timestamp, tz=timezone.utc)
            db.commit()
            # No need to refresh as we are done
    except Exception as e:
        logger.error(f"Error updating last_login for user_id={user_id}: {str(e)}")
        db.rollback()
    finally:
        db.close()
