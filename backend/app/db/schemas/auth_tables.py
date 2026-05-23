from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "user"

    id = Column(String, primary_key=True)
    name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    emailVerified = Column(Boolean, nullable=False, default=False)
    image = Column(Text)
    createdAt = Column(DateTime(timezone=True), nullable=False)
    updatedAt = Column(DateTime(timezone=True), nullable=False)
    role = Column(Text)
    banned = Column(Boolean)
    banReason = Column(Text)
    banExpires = Column(DateTime(timezone=True))
    customerId = Column(Text)

    sessions = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    accounts = relationship(
        "Account", back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "session"

    id = Column(String, primary_key=True)
    expiresAt = Column(DateTime(timezone=True), nullable=False)
    token = Column(Text, unique=True, nullable=False)
    createdAt = Column(DateTime(timezone=True), nullable=False)
    updatedAt = Column(DateTime(timezone=True), nullable=False)
    ipAddress = Column(Text)
    userAgent = Column(Text)
    userId = Column(String, ForeignKey("user.id"), nullable=False)

    user = relationship("User", back_populates="sessions")


class Account(Base):
    __tablename__ = "account"

    id = Column(String, primary_key=True)
    accountId = Column(Text, nullable=False)
    providerId = Column(Text, nullable=False)
    userId = Column(String, ForeignKey("user.id"), nullable=False)
    accessToken = Column(Text)
    refreshToken = Column(Text)
    idToken = Column(Text)
    accessTokenExpiresAt = Column(DateTime(timezone=True))
    refreshTokenExpiresAt = Column(DateTime(timezone=True))
    scope = Column(Text)
    password = Column(Text)
    createdAt = Column(DateTime(timezone=True), nullable=False)
    updatedAt = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="accounts")


class Verification(Base):
    __tablename__ = "verification"

    id = Column(String, primary_key=True)
    identifier = Column(Text, nullable=False)
    value = Column(Text, nullable=False)
    expiresAt = Column(DateTime(timezone=True), nullable=False)
    createdAt = Column(DateTime(timezone=True))
    updatedAt = Column(DateTime(timezone=True))


class BetterAuthSubscription(Base):
    __tablename__ = "subscription"

    id = Column(String, primary_key=True)
    plan = Column(String, nullable=False)
    referenceId = Column(String, nullable=False)
    stripeCustomerId = Column(String)
    stripeSubscriptionId = Column(String)
    status = Column(String, nullable=False, default="incomplete")
    periodStart = Column(DateTime(timezone=True))
    periodEnd = Column(DateTime(timezone=True))
    cancelAtPeriodEnd = Column(
        String
    )  # Sometimes boolean, sometimes string depending on DB? Better Auth uses boolean in docs.
    # We'll use String or Boolean based on the DB check. The docs say boolean.
    cancelAt = Column(DateTime(timezone=True))
    canceledAt = Column(DateTime(timezone=True))
    endedAt = Column(DateTime(timezone=True))
    trialStart = Column(DateTime(timezone=True))
    trialEnd = Column(DateTime(timezone=True))
