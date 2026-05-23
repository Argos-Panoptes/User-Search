from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class AppUser(Base):
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, index=True)
    auth_user_id = Column(
        String, ForeignKey("user.id"), unique=True, index=True, nullable=True
    )
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

    # Per-user API limits (NULL = use system defaults from config)
    rate_limit_per_minute = Column(Integer, nullable=True)  # custom rate limit, NULL = default
    max_api_keys = Column(Integer, nullable=True)  # max keys allowed, NULL = default

    # Bcrypt hash of the user's API access password (NULL = not set)
    api_password_hash = Column(String, nullable=True)

    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    payment_transactions = relationship(
        "PaymentTransaction",
        back_populates="user",
        order_by="desc(PaymentTransaction.created_at)",
    )

    @property
    def total_spent(self) -> float:
        if not self.payment_transactions:
            return 0.0
        return float(
            sum(
                t.amount
                for t in self.payment_transactions
                if t.status == "succeeded"
                and t.event_type == "invoice_payment"
                and t.amount is not None
            )
        )

    @property
    def total_payments(self) -> int:
        if not self.payment_transactions:
            return 0
        return len(
            [
                t
                for t in self.payment_transactions
                if t.status == "succeeded" and t.event_type == "invoice_payment"
            ]
        )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)  # Store as string, parse as needed
    description = Column(String, nullable=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
