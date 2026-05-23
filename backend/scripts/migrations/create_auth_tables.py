from app.db.session import engine
from app.db.base import Base
from app.db.schemas.auth_tables import User, Session, Account, Verification
from app.db.schemas.app_models import AppUser
from app.db.schemas.stripe_models import Subscription, PaymentTransaction


def create_tables():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


if __name__ == "__main__":
    create_tables()
