from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=False)
    stripe_customer_id = Column(String, index=True, nullable=False)
    status = Column(
        String, nullable=False, index=True
    )  # active, past_due, canceled, etc.
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )

    # Relationship
    user = relationship("AppUser", back_populates="subscription")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("app_users.id"), nullable=True, index=True
    )  # Nullable because we might receive webhook before linking? unlikely but safe
    stripe_transaction_id = Column(String, index=True)  # invoice id or charge id
    amount = Column(Numeric(10, 2))  # Store as decimal
    currency = Column(String(3))
    status = Column(String, index=True)  # succeeded, failed, pending
    event_type = Column(String, index=True)  # invoice.payment_succeeded, etc.
    raw_data = Column(JSON)  # Store full webhook payload/event data for audit

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    user = relationship("AppUser", back_populates="payment_transactions")

    @property
    def invoice_url(self) -> str | None:
        if not self.raw_data:
            return None
        return self.raw_data.get("hosted_invoice_url") or self.raw_data.get("invoice_pdf")
