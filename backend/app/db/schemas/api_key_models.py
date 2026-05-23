from sqlalchemy import (
    Column,
    Index,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_id = Column(String(64), unique=True, index=True, nullable=False)
    key_hash = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    created_by_id = Column(Integer, ForeignKey("app_users.id"), nullable=False)
    created_by = relationship("AppUser", foreign_keys=[created_by_id])

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    quota_limit = Column(Integer, nullable=True)  # requests per minute, NULL = default
    allowed_endpoints = Column(JSON, nullable=True)  # list of endpoint patterns, NULL = all
    metadata_json = Column(JSON, nullable=True)

    request_count = Column(BigInteger, default=0, nullable=False)


class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_key_id = Column(String(64), ForeignKey("api_keys.key_id"), nullable=False, index=True)
    endpoint = Column(String(512), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_agent = Column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_request_logs_key_ts", "api_key_id", "timestamp"),
        Index("ix_request_logs_endpoint_ts", "endpoint", "timestamp"),
    )
