from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    BigInteger,
    Boolean,
    UniqueConstraint,
    Float,
    LargeBinary,
    Index,
    text,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base
from datetime import datetime

from typing import Any, TYPE_CHECKING


if TYPE_CHECKING:
    from app.db.schemas.app_models import AppUser


class UserMetadata(Base):
    __tablename__: str = "user_metadata"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    service_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    e164: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_name: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_family_name: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    active_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    profile_last_fetched_at: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    about_emoji: Mapped[str | None] = mapped_column(String, nullable=True)
    remote_avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_key: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_key_version: Mapped[str | None] = mapped_column(String, nullable=True)
    access_key: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_key_credential: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_key_credential_expiration: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    sharing_phone_number: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    capabilities: Mapped[str | None] = mapped_column(String, nullable=True)
    verified: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_id: Mapped[str | None] = mapped_column(String, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_admin: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False, index=True
    )

    avatar_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("avatars.id"), nullable=True
    )
    export_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_updated_job_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    snapshot_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, index=True
    )

    first_observed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_observed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class GroupMetadata(Base):
    __tablename__: str = "groups"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    group_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    group_name: Mapped[str | None] = mapped_column(String, nullable=True)
    number_of_members: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admin_approval_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    group_link: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_period: Mapped[str | None] = mapped_column(String, nullable=True)
    master_key: Mapped[str | None] = mapped_column(String, nullable=True)
    invite_link_password: Mapped[str | None] = mapped_column(String, nullable=True)
    secret_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconstructed_link: Mapped[str | None] = mapped_column(String, nullable=True)
    export_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_updated_job_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    snapshot_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, index=True
    )

    first_observed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_observed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# --- New Job/Progress/Log Models ---


class IngestionJob(Base):
    __tablename__: str = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(
        String, unique=True, index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String, default="pending", index=True
    )  # pending, running, completed, failed
    ingestion_type: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # "users", "groups", "avatars"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("app_users.id"), nullable=True
    )
    created_by_user: Mapped["AppUser"] = relationship(
        "AppUser", backref="ingestion_jobs"
    )
    steps: Mapped[list["IngestionStep"]] = relationship(
        "IngestionStep", back_populates="job", cascade="all, delete-orphan"
    )
    logs: Mapped[list["IngestionLog"]] = relationship(
        "IngestionLog", back_populates="job", cascade="all, delete-orphan"
    )


class IngestionStep(Base):
    __tablename__: str = "ingestion_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingestion_jobs.id"), nullable=False, index=True
    )

    step_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # pending, running, completed, failed
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    current_action: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # E.g. "Unzipping", "Batch 1/5"

    # Relationship to Substeps
    substeps: Mapped[list["IngestionSubstep"]] = relationship(
        "IngestionSubstep", back_populates="step", cascade="all, delete-orphan"
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job = relationship("IngestionJob", back_populates="steps")


class IngestionSubstep(Base):
    __tablename__: str = "ingestion_substeps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    step_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingestion_steps.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # pending, running, completed, failed

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    step: Mapped["IngestionStep"] = relationship(
        "IngestionStep", back_populates="substeps"
    )


class IngestionLog(Base):
    __tablename__: str = "ingestion_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingestion_jobs.id"), nullable=False, index=True
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    log_level: Mapped[str] = mapped_column(String, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    step_name: Mapped[str | None] = mapped_column(String, nullable=True)

    job: Mapped["IngestionJob"] = relationship("IngestionJob", back_populates="logs")


# --- New Content Features Models ---


class Avatar(Base):
    __tablename__: str = "avatars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_id: Mapped[str] = mapped_column(
        String, index=True
    )  # Link to UserMetadata.service_id (Non-unique to allow history)

    s3_key: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True, index=True
    )
    s3_url: Mapped[str | None] = mapped_column(String, nullable=True)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_updated_job_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    snapshot_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, index=True
    )

    # Avatar Sync (Part B) - Scheduled Revalidation columns
    stored_etag: Mapped[str | None] = mapped_column(String, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # unverified, verified, changed, etag_variance, failed, missing
    change_frequency: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # HIGH, MEDIUM, LOW — auto-adjusted based on change patterns
    failure_reason: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # S3_HEAD_ERROR, DOWNLOAD_TIMEOUT, DOWNLOAD_FAILED, etc.

    # Optional: Relationship back to User?
    user: Mapped["UserMetadata"] = relationship(
        "UserMetadata",
        foreign_keys=[service_id],
        primaryjoin="UserMetadata.service_id == Avatar.service_id",
    )


class AvatarSyncAuditLog(Base):
    """Audit log for avatar sync revalidation (Part B). Tracks changes, missing, and errors."""

    __tablename__: str = "avatar_sync_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    avatar_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    service_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "changed", "missing", "error", "etag_updated"
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    new_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    old_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    old_s3_url: Mapped[str | None] = mapped_column(String, nullable=True)
    new_s3_url: Mapped[str | None] = mapped_column(String, nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GroupMembershipMap(Base):
    __tablename__: str = "group_memberships_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_metadata.id"), nullable=False, index=True
    )
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("groups.id"), nullable=False, index=True
    )
    role: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # e.g. "admin", "member"

    # Unique constraint to prevent duplicate memberships
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_user_group_membership"),
    )


# --- History Models ---


class UserHistory(Base):
    __tablename__: str = "user_history"

    history_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    history_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    history_operation: Mapped[str] = mapped_column(String)  # INSERT, UPDATE, DELETE

    # Mirror of User Identity
    service_id: Mapped[str] = mapped_column(String, index=True)

    # Mirrored columns for querying
    e164: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_name: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_family_name: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    active_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    profile_last_fetched_at: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    about_emoji: Mapped[str | None] = mapped_column(String, nullable=True)
    remote_avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_key: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_key_version: Mapped[str | None] = mapped_column(String, nullable=True)
    access_key: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_key_credential: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_key_credential_expiration: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    sharing_phone_number: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    capabilities: Mapped[str | None] = mapped_column(String, nullable=True)
    verified: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_id: Mapped[str | None] = mapped_column(String, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_admin: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    export_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    avatar_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metadata for Rollback/Diff
    last_updated_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, index=True
    )

    # Link to Central Ledger
    timeline_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Cannot be FK in partitioned table easily

    __table_args__: Any = (
        Index(
            "idx_user_history_lookup",
            "service_id",
            "history_date",
            postgresql_using="btree",
        ),
        Index("idx_user_history_brin", "history_date", postgresql_using="brin"),
        {"postgresql_partition_by": "RANGE (history_date)"},
    )


class GroupHistory(Base):
    __tablename__: str = "group_history"

    history_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    history_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    history_operation: Mapped[str] = mapped_column(String)  # INSERT, UPDATE, DELETE

    # Mirror of Group Identity
    group_id: Mapped[str] = mapped_column(String, index=True)

    # Mirrored columns for querying
    group_name: Mapped[str | None] = mapped_column(String, nullable=True)
    number_of_members: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admin_approval_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    group_link: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_period: Mapped[str | None] = mapped_column(String, nullable=True)
    master_key: Mapped[str | None] = mapped_column(String, nullable=True)
    invite_link_password: Mapped[str | None] = mapped_column(String, nullable=True)
    secret_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconstructed_link: Mapped[str | None] = mapped_column(String, nullable=True)

    # Metadata for Rollback/Diff
    last_updated_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, index=True
    )

    # Link to Group Timeline Ledger
    timeline_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Cannot be FK in partitioned table easily

    __table_args__: Any = (
        Index(
            "idx_group_history_lookup",
            "group_id",
            "history_date",
            postgresql_using="btree",
        ),
        Index("idx_group_history_brin", "history_date", postgresql_using="brin"),
        {"postgresql_partition_by": "RANGE (history_date)"},
    )


class AvatarHistory(Base):
    __tablename__: str = "avatar_history"

    history_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    history_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    history_operation: Mapped[str] = mapped_column(String)  # INSERT, UPDATE, DELETE

    # Mirror of Avatar Identity
    id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # original PK
    service_id: Mapped[str] = mapped_column(String, index=True)

    # Mirrored columns for querying
    s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    s3_url: Mapped[str | None] = mapped_column(String, nullable=True)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata for Rollback/Diff
    last_updated_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, index=True
    )

    # Link to Central Ledger (User Perspective)
    timeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__: Any = (
        Index(
            "idx_avatar_history_lookup",
            "service_id",
            "history_date",
            postgresql_using="btree",
        ),
        Index("idx_avatar_history_brin", "history_date", postgresql_using="brin"),
        {"postgresql_partition_by": "RANGE (history_date)"},
    )


class UserTimelineLedger(Base):
    """
    Central Ledger for tracking ANY change to a user (Profile, Membership, Avatar).
    One entry per (User, Job).
    """

    __tablename__: str = "user_timeline_ledger"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    export_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False, index=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_metadata.id"), nullable=False, index=True
    )
    service_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Change Flags
    has_profile_change: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False
    )
    has_membership_change: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False
    )
    has_avatar_change: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Ensure idempotency per job
    __table_args__: Any = (
        Index(
            "uq_user_timeline_job", "user_id", "job_id", "export_timestamp", unique=True
        ),
        Index(
            "idx_user_timeline_service_id_ts",
            "service_id",
            "export_timestamp",
            postgresql_using="btree",
        ),
        Index("idx_user_timeline_brin", "export_timestamp", postgresql_using="brin"),
        {"postgresql_partition_by": "RANGE (export_timestamp)"},
    )


class GroupTimelineLedger(Base):
    """
    Central Ledger for tracking ANY change to a group (Details, Memberships).
    One entry per (Group, Job).
    """

    __tablename__: str = "group_timeline_ledger"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    export_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False, index=True
    )

    group_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("groups.id"), nullable=False, index=True
    )
    group_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Change Flags
    has_detail_change: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False
    )
    has_membership_change: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Ensure idempotency per job
    __table_args__: Any = (
        Index(
            "uq_group_timeline_job",
            "group_pk",
            "job_id",
            "export_timestamp",
            unique=True,
        ),
        Index(
            "idx_group_timeline_group_id_ts",
            "group_id",
            "export_timestamp",
            postgresql_using="btree",
        ),
        Index("idx_group_timeline_brin", "export_timestamp", postgresql_using="brin"),
        {"postgresql_partition_by": "RANGE (export_timestamp)"},
    )


class GroupMembershipHistory(Base):
    """
    SCD Type 2 History for Group Memberships.
    Allows efficient querying of:
    - User's group history: SELECT * FROM ... WHERE user_id = X
    - Group's member history: SELECT * FROM ... WHERE group_id = Y
    """

    __tablename__: str = "group_membership_history"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now(), index=True
    )

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)  # 'admin', 'member'
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)

    # Validity Range (To)
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )  # NULL = Active

    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Link to Central Ledger
    join_timeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    join_group_timeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_timeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_group_timeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__: Any = (
        Index(
            "idx_membership_history_user",
            "user_id",
            "valid_from",
            "valid_to",
            postgresql_using="btree",
        ),
        Index(
            "idx_membership_history_group",
            "group_id",
            "valid_from",
            "valid_to",
            postgresql_using="btree",
        ),
        Index("idx_membership_history_brin", "valid_from", postgresql_using="brin"),
        {"postgresql_partition_by": "RANGE (valid_from)"},
    )


class UserExclusionList(Base):
    """
    Tracks excluded/deleted users. Serves as both:
    1. Audit log of all user deletions (who, when, why)
    2. Re-ingestion blocklist (prevents resurrection via future data imports)
    """

    __tablename__: str = "user_exclusion_list"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    service_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    reason: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_by: Mapped[str] = mapped_column(
        String, nullable=False
    )  # admin email
    deleted_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("app_users.id"), nullable=True
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Snapshot of user info at time of deletion (for audit display)
    user_name: Mapped[str | None] = mapped_column(String, nullable=True)
    user_e164: Mapped[str | None] = mapped_column(String, nullable=True)
