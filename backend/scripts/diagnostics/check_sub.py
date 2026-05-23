import sys
import os

sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.db.schemas.stripe_models import Subscription
from app.core.config import settings

print(f"ENABLE_AUTH: {settings.ENABLE_AUTH}")

db = SessionLocal()
try:
    sub = db.query(Subscription).filter(Subscription.user_id == 1).first()
    if sub:
        print(f"Subscription Status: {sub.status}")
        print(f"Subscription ID: {sub.id}")
        print(f"Current Period End: {sub.current_period_end}")
    else:
        print("No subscription found for user 1")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
