"""
Avatar Sync Part B: Continuous Scheduled CDN Fetch & Sync

Fetches avatars from Signal's CDN using remoteAvatarUrl + profileKey from
user_metadata, decrypts with AES-256-GCM, compares SHA-256 hash against
existing avatars, and uploads changed/new avatars to S3.

Architecture:
- Beat triggers `trigger_scheduled_avatar_sync` at 2:30 AM daily
- Trigger creates an IngestionJob, shards the ID range, dispatches N batches
- `run_avatar_sync_batch` processes BATCH_SIZE users using smart filtering
  with ThreadPoolExecutor for parallel CDN fetch + decrypt + S3 upload,
  then re-queues itself with countdown delay (cooperative multitasking)

Smart Filtering:
- Users whose linked avatar has change_frequency=HIGH are re-checked every 6 hours
- MEDIUM every 3 days, LOW every 7 days
- Users with no avatar or never-verified are checked within 24 hours

Parallelism:
- Connection-pooled requests.Session with urllib3 retry
- ThreadPoolExecutor for concurrent CDN fetches within each batch
- Token bucket rate limiter across threads
- ID-range sharding across multiple Celery workers
"""

import base64
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
import urllib3
from celery import Task

# Suppress noisy SSL warnings for Signal CDN (verify=False is required)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from celery.exceptions import Retry
from Crypto.Cipher import AES
from requests.adapters import HTTPAdapter
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from urllib3.util.retry import Retry as Urllib3Retry

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging import logger
from app.core.s3 import get_s3_client, put_s3_object, delete_s3_object, get_s3_object_body
from app.db.session import SessionLocal
from app.db.schemas.ingestion_models import (
    Avatar,
    AvatarSyncAuditLog,
    IngestionJob,
    UserMetadata,
)
from app.controllers.jobs_controller import JobsController
from app.utils.ingestion_helpers import (
    get_job_db_logger,
    _ensure_steps_generic,
    _get_step_id,
    _update_action,
)
from app.utils.system_check import is_storage_critical, get_disk_usage_percent
from app.utils.avatar_sync_utils import (
    build_smart_filter_query,
    update_change_frequency,
    check_alert_threshold,
    _get_setting_int,
    _get_setting_float,
)
from app.utils.avatar_sync_audit import log_avatar_sync_audit


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILE_IV_LENGTH = 12
PROFILE_KEY_LENGTH = 32
GCM_TAG_LENGTH = 16


# ---------------------------------------------------------------------------
# Module-level infrastructure: HTTP session, thread pool, rate limiter
# ---------------------------------------------------------------------------

_retry_strategy = Urllib3Retry(
    total=1,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503],
)
_http_adapter = HTTPAdapter(
    pool_connections=20,
    pool_maxsize=32,
    max_retries=_retry_strategy,
)
_cdn_session = requests.Session()
_cdn_session.mount("https://", _http_adapter)
_cdn_session.mount("http://", _http_adapter)

_fetch_pool = ThreadPoolExecutor(max_workers=settings.AVATAR_SYNC_THREAD_POOL_SIZE)


class _TokenBucket:
    """Thread-safe token bucket for CDN rate limiting."""

    def __init__(self, rate: float):
        self._rate = rate
        self._tokens = rate
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self):
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self._rate,
                    self._tokens + (now - self._last) * self._rate,
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            time.sleep(0.05)


_cdn_rate_limiter = _TokenBucket(settings.AVATAR_SYNC_CDN_REQUESTS_PER_SEC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fail_job(db: Session, job_id: int, error_msg: str) -> None:
    """Mark job as failed with error message."""
    job = JobsController.get_job(db, job_id)
    if job:
        job.status = "failed"
        job.error_message = error_msg
        job.completed_at = datetime.now(timezone.utc)
        db.commit()


def _enforce_storage_limit(db: Session, job_id: int, db_log) -> None:
    """Check storage before heavy work."""
    if is_storage_critical(threshold=0.9):
        usage = get_disk_usage_percent() * 100
        error_msg = (
            f"Avatar sync aborted: System storage usage is at {usage:.1f}%. "
            "Please increase storage capacity to proceed."
        )
        db_log(error_msg, level="ERROR")
        _fail_job(db, job_id, error_msg)
        raise Exception(error_msg)


def _check_and_queue_if_blocked(
    db: Session, job_id: int, db_log, retry_exc
) -> None:
    """FIFO enforcement for avatar_sync jobs."""
    older_active_job = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.ingestion_type == "avatar_sync",
            IngestionJob.id < job_id,
            IngestionJob.status.in_(["running", "queued", "pending", "initializing"]),
        )
        .first()
    )

    if older_active_job:
        current_job = JobsController.get_job(db, job_id)
        if current_job and current_job.status != "queued":
            current_job.status = "queued"
            db.commit()
            db_log(
                f"Avatar sync queued. Waiting for Job #{older_active_job.id} "
                f"(Status: {older_active_job.status}) to finish...",
                level="INFO",
            )
        raise retry_exc(countdown=10)

    JobsController.mark_job_running(db, job_id)


def _is_valid_image(data: bytes) -> bool:
    """Check magic bytes for JPEG, PNG, WEBP, GIF."""
    return (
        data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"\x89PNG")
        or data.startswith(b"RIFF")
        or data.startswith(b"GIF8")
    )


def _detect_extension(data: bytes) -> str:
    """Detect file extension from image magic bytes."""
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"RIFF"):
        return ".webp"
    if data.startswith(b"GIF8"):
        return ".gif"
    return ".jpg"


def _detect_content_type(data: bytes) -> str:
    """Detect MIME content type from image magic bytes."""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"RIFF"):
        return "image/webp"
    if data.startswith(b"GIF8"):
        return "image/gif"
    return "image/jpeg"


def _is_unencrypted_image(data: bytes) -> bool:
    """Check if data is already an unencrypted image (no decryption needed)."""
    return _is_valid_image(data)


def _build_s3_url(s3_key: str) -> str:
    """Build the MinIO S3 URL for an uploaded avatar."""
    return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET_NAME}/{s3_key}"


def _demote_change_frequency(current: str | None) -> str:
    """Compute demoted change_frequency for unchanged avatars (pure function)."""
    if current is None:
        return "LOW"
    if current == "HIGH":
        return "MEDIUM"
    if current == "MEDIUM":
        return "LOW"
    return current  # LOW stays LOW


# ---------------------------------------------------------------------------
# Core sync logic: split into thread-safe fetch + single-threaded DB apply
# ---------------------------------------------------------------------------


def _fetch_and_decrypt(
    user_info: dict,
    avatar_info: dict | None,
    session: requests.Session,
    cdn_timeout: int | None = None,
    ssim_threshold: float | None = None,
) -> dict:
    """
    Fetch and decrypt a single user's avatar from Signal CDN. Thread-safe.

    No DB access — operates on plain dicts, not ORM objects.
    Handles: CDN fetch, AES-256-GCM decryption, hash comparison, S3 upload/delete.

    Returns a result dict with status and all info needed for DB updates.
    """
    result = {
        "status": "error",
        "user_info": user_info,
        "avatar_info": avatar_info,
        "decrypted": None,
        "new_hash": None,
        "s3_key": None,
        "s3_url": None,
        "old_s3_key_deleted": False,
        "file_size": None,
        "ext": None,
        "error_detail": None,
        "failure_reason": None,
        "ssim_score": None,
        "hash_changed_but_visually_same": False,
    }

    service_id = user_info["service_id"]

    # --- Step 1: Fetch from CDN ---
    remote_url = user_info["remote_avatar_url"]
    if remote_url.startswith("profiles/"):
        path = remote_url
    else:
        path = f"profiles/{remote_url}"

    cdn_url = f"{settings.AVATAR_SYNC_CDN_BASE_URL.rstrip('/')}/{path}"

    # Rate limit before making the request
    _cdn_rate_limiter.acquire()

    try:
        response = session.get(
            cdn_url,
            timeout=cdn_timeout or settings.AVATAR_SYNC_CDN_TIMEOUT,
            verify=settings.AVATAR_SYNC_CDN_VERIFY_SSL,
        )
    except requests.RequestException as e:
        result["failure_reason"] = f"CDN_FETCH_ERROR: {str(e)[:60]}"
        result["error_detail"] = f"CDN fetch failed for user {service_id}: {str(e)[:200]}"
        logger.warning(f"CDN fetch failed for {service_id}: {e}")
        return result

    if response.status_code in (403, 404):
        result["status"] = "missing"
        result["failure_reason"] = f"CDN_HTTP_{response.status_code}"
        result["error_detail"] = (
            f"Avatar inaccessible on CDN ({response.status_code}) for user {service_id}"
        )
        return result

    if response.status_code != 200:
        result["failure_reason"] = f"CDN_HTTP_{response.status_code}"
        result["error_detail"] = (
            f"CDN HTTP {response.status_code} error for user {service_id} (URL: {cdn_url})"
        )
        logger.warning(f"CDN returned HTTP {response.status_code} for {service_id}")
        return result

    encrypted_data = response.content
    if len(encrypted_data) == 0:
        result["failure_reason"] = "CDN_EMPTY_RESPONSE"
        result["error_detail"] = f"CDN returned empty response for user {service_id}"
        return result

    # --- Step 2: Decrypt ---
    if _is_unencrypted_image(encrypted_data):
        decrypted = encrypted_data
    else:
        if len(encrypted_data) < PROFILE_IV_LENGTH + GCM_TAG_LENGTH:
            result["failure_reason"] = "ENCRYPTED_DATA_TOO_SHORT"
            result["error_detail"] = (
                f"Encrypted data too short for user {service_id} "
                f"({len(encrypted_data)} bytes, need at least {PROFILE_IV_LENGTH + GCM_TAG_LENGTH})"
            )
            return result

        try:
            profile_key_bytes = base64.b64decode(user_info["profile_key"])
            if len(profile_key_bytes) != PROFILE_KEY_LENGTH:
                raise ValueError(
                    f"Key length {len(profile_key_bytes)}, expected {PROFILE_KEY_LENGTH}"
                )
        except Exception as e:
            result["failure_reason"] = "INVALID_PROFILE_KEY"
            result["error_detail"] = (
                f"Invalid profile key for user {service_id}: {str(e)[:100]}"
            )
            return result

        iv = encrypted_data[:PROFILE_IV_LENGTH]
        ciphertext_with_tag = encrypted_data[PROFILE_IV_LENGTH:]
        ciphertext = ciphertext_with_tag[:-GCM_TAG_LENGTH]
        tag = ciphertext_with_tag[-GCM_TAG_LENGTH:]

        try:
            cipher = AES.new(profile_key_bytes, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        except ValueError:
            result["failure_reason"] = "GCM_TAG_MISMATCH"
            result["error_detail"] = (
                f"AES-GCM tag verification failed for user {service_id}"
            )
            logger.warning(f"GCM tag mismatch for {service_id}")
            return result
        except Exception as e:
            result["failure_reason"] = "DECRYPTION_FAILED"
            result["error_detail"] = (
                f"Decryption failed for user {service_id}: {str(e)[:150]}"
            )
            logger.warning(f"Decryption failed for {service_id}: {e}")
            return result

    # Validate decrypted data is an image
    if not _is_valid_image(decrypted):
        result["failure_reason"] = "NOT_AN_IMAGE"
        result["error_detail"] = (
            f"Decrypted data is not a valid image for user {service_id} "
            f"(first bytes: {decrypted[:4].hex() if decrypted else 'empty'})"
        )
        return result

    # --- Step 3: Hash comparison + SSIM visual comparison ---
    new_hash = hashlib.sha256(decrypted).digest()
    result["new_hash"] = new_hash
    result["file_size"] = len(decrypted)

    # Fast path: byte-identical (hash match)
    if avatar_info and avatar_info["snapshot_hash"] == new_hash:
        result["status"] = "unchanged"
        return result

    # Slow path: hash differs, but check visual similarity via SSIM
    if avatar_info and avatar_info["s3_key"]:
        try:
            existing_bytes = get_s3_object_body(avatar_info["s3_key"])
            if existing_bytes is not None:
                from app.utils.image_similarity import compute_ssim

                similarity = compute_ssim(existing_bytes, decrypted)
                result["ssim_score"] = similarity
                if similarity >= (ssim_threshold or settings.AVATAR_SYNC_SSIM_THRESHOLD):
                    result["status"] = "unchanged"
                    result["hash_changed_but_visually_same"] = True
                    return result
        except Exception as e:
            logger.warning(
                f"SSIM comparison failed for {service_id}, treating as changed: {e}"
            )

    # --- Step 4: Changed or new — upload to S3 ---
    ext = _detect_extension(decrypted)
    hash_hex = new_hash.hex()[:16]
    s3_key = f"avatars/{service_id}_{hash_hex}{ext}"
    result["ext"] = ext
    result["decrypted"] = decrypted

    if get_s3_client() is not None:
        content_type = _detect_content_type(decrypted)
        try:
            put_s3_object(s3_key, decrypted, content_type)
            result["s3_key"] = s3_key
            result["s3_url"] = _build_s3_url(s3_key)

            # Delete old S3 object if avatar changed (not new)
            if avatar_info and avatar_info["s3_key"] and avatar_info["s3_key"] != s3_key:
                try:
                    delete_s3_object(avatar_info["s3_key"])
                    result["old_s3_key_deleted"] = True
                except Exception as e:
                    logger.warning(
                        f"Failed to delete old avatar {avatar_info['s3_key']}: {e}"
                    )
        except Exception as e:
            logger.warning(f"S3 upload failed for {service_id}: {e}")
            result["error_detail"] = (
                f"MinIO upload failed for user {service_id}: {str(e)[:150]}"
            )

    if avatar_info:
        result["status"] = "changed"
    else:
        result["status"] = "new"

    return result


def _apply_results_to_db(
    db: Session,
    results: list[dict],
    job_id: int,
    stats: dict,
    db_log,
    orm_lookup: dict,
) -> None:
    """
    Apply all fetch/decrypt results to the database in a single transaction.

    orm_lookup: {user_meta_id: (UserMetadata_orm, Avatar_orm_or_None)}
    """
    now = datetime.now(timezone.utc)
    unchanged_updates = []

    for r in results:
        user_info = r["user_info"]
        avatar_info = r["avatar_info"]
        status = r["status"]
        user_meta_id = user_info["id"]
        service_id = user_info["service_id"]

        user_meta_orm, existing_avatar = orm_lookup.get(
            user_meta_id, (None, None)
        )

        stats["checked"] += 1

        if status == "unchanged":
            stats["unchanged"] += 1
            if existing_avatar:
                new_freq = _demote_change_frequency(existing_avatar.change_frequency)
                update_dict = {
                    "id": existing_avatar.id,
                    "last_verified_at": now,
                    "verification_status": "verified",
                    "failure_reason": None,
                    "change_frequency": new_freq,
                }
                # If hash changed but visually same (SSIM match), update stored hash
                # so the fast-path hash check works on the next sync cycle
                if r.get("hash_changed_but_visually_same") and r.get("new_hash"):
                    update_dict["snapshot_hash"] = r["new_hash"]
                unchanged_updates.append(update_dict)

        elif status == "changed":
            stats["changed"] += 1
            if existing_avatar:
                old_hash = existing_avatar.snapshot_hash
                old_size = existing_avatar.file_size
                old_s3_url = existing_avatar.s3_url

                if r["s3_url"]:
                    hash_hex = r["new_hash"].hex()[:16]
                    existing_avatar.s3_key = r["s3_key"]
                    existing_avatar.s3_url = r["s3_url"]
                    existing_avatar.filename = f"{service_id}_{hash_hex}{r['ext']}"

                existing_avatar.file_size = r["file_size"]
                existing_avatar.snapshot_hash = r["new_hash"]
                existing_avatar.last_verified_at = now
                existing_avatar.verification_status = "changed"
                existing_avatar.failure_reason = None
                existing_avatar.last_updated_job_id = job_id
                update_change_frequency(existing_avatar, changed=True)

                old_hash_hex = old_hash.hex() if old_hash else "none"
                new_hash_hex = r["new_hash"].hex()
                log_avatar_sync_audit(
                    db, existing_avatar, "changed",
                    f"Hash changed: {old_hash_hex[:16]}... -> {new_hash_hex[:16]}...",
                    job_id,
                    old_hash=old_hash, new_hash=r["new_hash"],
                    old_file_size=old_size, new_file_size=r["file_size"],
                    old_s3_url=old_s3_url, new_s3_url=r["s3_url"],
                )

        elif status == "new":
            stats["new"] += 1
            hash_hex = r["new_hash"].hex()[:16]
            new_avatar = Avatar(
                service_id=service_id,
                s3_key=r["s3_key"] if r["s3_url"] else None,
                s3_url=r["s3_url"],
                filename=f"{service_id}_{hash_hex}{r['ext']}" if r["s3_url"] else None,
                file_size=r["file_size"],
                timestamp=now,
                snapshot_hash=r["new_hash"],
                last_verified_at=now,
                verification_status="new",
                change_frequency="MEDIUM",
                last_updated_job_id=job_id,
            )
            db.add(new_avatar)
            db.flush()

            if user_meta_orm:
                user_meta_orm.avatar_id = new_avatar.id

            log_avatar_sync_audit(
                db, new_avatar, "new",
                f"New avatar detected from CDN ({r['file_size']} bytes)",
                job_id,
                new_hash=r["new_hash"], new_file_size=r["file_size"],
                new_s3_url=r["s3_url"],
            )

        elif status == "missing":
            stats["missing"] += 1
            if existing_avatar:
                existing_avatar.last_verified_at = now
                existing_avatar.verification_status = "missing"
                existing_avatar.failure_reason = "CDN_AVATAR_NOT_FOUND"
                update_change_frequency(existing_avatar, changed=False)
                log_avatar_sync_audit(
                    db, existing_avatar, "missing",
                    "Avatar not found on CDN (404)", job_id,
                )

        elif status == "error":
            stats["errors"] += 1
            if existing_avatar:
                existing_avatar.verification_status = "failed"
                existing_avatar.failure_reason = r.get("failure_reason", "UNKNOWN")
                existing_avatar.last_verified_at = now
                update_change_frequency(existing_avatar, changed=False)

                log_avatar_sync_audit(
                    db, existing_avatar, "error",
                    f"{r.get('error_detail', 'Unknown error')[:200]}",
                    job_id,
                )
            # Skip audit log when no existing avatar — avatar_id is NOT NULL
            # and errors for users without avatars are captured in job-level stats

    # Bulk update all unchanged avatars in one call
    if unchanged_updates:
        db.bulk_update_mappings(Avatar, unchanged_updates)

    db.commit()


# ---------------------------------------------------------------------------
# Task 1: Beat-triggered scheduler (runs on default queue)
# ---------------------------------------------------------------------------


@celery_app.task(name="avatar_sync_tasks.trigger_scheduled_avatar_sync")
def trigger_scheduled_avatar_sync():
    """
    Scheduled task to trigger avatar sync.

    Checks:
    1. AVATAR_SYNC_ENABLED kill switch
    2. S3 configured
    3. SystemSetting override for interval
    4. No running avatar_sync job
    5. Enough time since last run

    Then shards the user ID range and dispatches N parallel batch workers.
    """
    from app.db.schemas.app_models import SystemSetting

    if get_s3_client() is None:
        logger.info("Avatar sync skipped: S3 not configured.")
        return

    db = SessionLocal()
    try:
        # 0. Check AVATAR_SYNC_ENABLED (SystemSetting override > env var)
        enabled_setting = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == "AVATAR_SYNC_ENABLED")
            .scalar()
        )
        is_enabled = settings.AVATAR_SYNC_ENABLED
        if enabled_setting and enabled_setting.value:
            is_enabled = enabled_setting.value.lower() == "true"

        if not is_enabled:
            return

        # 1. Get configured interval (allow SystemSetting override)
        interval_setting = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == "AVATAR_SYNC_INTERVAL_HOURS")
            .scalar()
        )

        interval_hours = settings.AVATAR_SYNC_INTERVAL_HOURS
        if interval_setting and interval_setting.value:
            try:
                interval_hours = int(interval_setting.value)
            except ValueError:
                logger.error(
                    f"Invalid avatar sync interval setting: {interval_setting.value}. "
                    "Using default."
                )

        # 2. Check for existing running job
        existing_job = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.ingestion_type == "avatar_sync",
                IngestionJob.status.in_(["running", "queued", "pending"]),
            )
            .first()
        )

        if existing_job:
            logger.info(
                f"Skipping scheduled avatar sync: Job {existing_job.id} is already "
                f"{existing_job.status}."
            )
            return

        # 3. Check last job time (throttle)
        last_job = (
            db.query(IngestionJob)
            .filter(IngestionJob.ingestion_type == "avatar_sync")
            .order_by(IngestionJob.created_at.desc())
            .first()
        )

        if last_job and last_job.created_at:
            now = datetime.now(timezone.utc)
            last_run = last_job.created_at
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)

            elapsed_hours = (now - last_run).total_seconds() / 3600

            if elapsed_hours < interval_hours:
                logger.info(
                    f"Skipping scheduled avatar sync: Last run was {elapsed_hours:.1f}h ago, "
                    f"interval is {interval_hours}h."
                )
                return

        # 4. Query ID range for sharding
        id_range = (
            db.query(
                sqla_func.min(UserMetadata.id),
                sqla_func.max(UserMetadata.id),
            )
            .filter(
                UserMetadata.remote_avatar_url.isnot(None),
                UserMetadata.profile_key.isnot(None),
            )
            .one()
        )
        min_id, max_id = id_range

        if min_id is None or max_id is None:
            logger.info("No users with avatar URLs found, skipping sync.")
            return

        # Count total eligible users for progress tracking
        total_eligible = (
            db.query(sqla_func.count(UserMetadata.id))
            .filter(
                UserMetadata.remote_avatar_url.isnot(None),
                UserMetadata.profile_key.isnot(None),
            )
            .scalar()
        ) or 0

        # 5. Create new job
        job = JobsController.create_job(
            db=db,
            ingestion_type="avatar_sync",
            celery_task_id=None,
        )

        # FIFO check
        _check_and_queue_if_blocked(db, job.id, get_job_db_logger(job.id), lambda countdown: None)

        # Storage check
        _enforce_storage_limit(db, job.id, get_job_db_logger(job.id))

        # Create steps for UI visibility
        _ensure_steps_generic(job.id, ["avatar_sync"])
        step_id = _get_step_id(job.id, "avatar_sync")
        JobsController.update_step_progress(db, step_id, 0.0, "running")
        _update_action(step_id, "Starting avatar sync (CDN fetch mode)...")

        db_log = get_job_db_logger(job.id)
        db_log(
            "Starting Avatar Sync — CDN Fetch Mode (smart filtering enabled)",
            level="INFO",
            step="avatar_sync",
        )

        # 6. Compute shards and dispatch
        shard_count = _get_setting_int(db, "AVATAR_SYNC_SHARD_COUNT", settings.AVATAR_SYNC_SHARD_COUNT)

        # Initialize metrics with shard tracking
        job.metrics = {
            "total_eligible": total_eligible,
            "total_checked": 0,
            "unchanged": 0,
            "changed": 0,
            "new": 0,
            "missing": 0,
            "errors": 0,
            "batches_processed": 0,
            "shard_count": shard_count,
            "shards_completed": 0,
        }
        job.started_at = datetime.now(timezone.utc)
        flag_modified(job, "metrics")
        db.commit()

        shard_size = (max_id - min_id + 1) // shard_count

        for i in range(shard_count):
            shard_start = min_id + (i * shard_size)
            if i < shard_count - 1:
                shard_end_val = min_id + ((i + 1) * shard_size) - 1
            else:
                shard_end_val = max_id

            # last_processed_id is exclusive (id > X), so use shard_start - 1
            run_avatar_sync_batch.apply_async(
                args=[job.id, shard_start - 1],
                kwargs={"shard_end": shard_end_val},
                queue="avatars",
            )

        logger.info(
            f"Dispatched {shard_count} shards for avatar sync job {job.id} "
            f"(ID range: {min_id}-{max_id}, Interval: {interval_hours}h)"
        )

    except Retry:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger scheduled avatar sync: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task 2: Batch worker (runs on avatars queue, self-re-queuing)
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    max_retries=2,
    name="avatar_sync_tasks.run_avatar_sync_batch",
)
def run_avatar_sync_batch(
    self: Task,
    job_id: int,
    last_processed_id: int = 0,
    shard_start: int | None = None,
    shard_end: int | None = None,
) -> dict | None:
    """
    Process a batch of users for avatar sync from Signal CDN.

    Smart filtering reduces workload by ~60%: only re-checks users whose
    linked avatar's change_frequency tier indicates they are due for verification.

    Uses ThreadPoolExecutor for parallel CDN fetch + decrypt + S3 upload,
    then applies all DB changes in a single transaction.

    Self-re-queues with countdown for the next batch, allowing other
    tasks to interleave (queue fairness).

    Includes timeout enforcement (default 1 hour hard limit) and
    alert logging if duration exceeds threshold (default 30 min).
    """
    db_log = get_job_db_logger(job_id)
    db = SessionLocal()

    try:
        # Validate job still exists and isn't cancelled
        job = JobsController.get_job(db, job_id)
        if not job or job.status == "failed":
            logger.info(f"Avatar sync job {job_id} no longer valid, stopping.")
            return None

        # Non-sharded legacy call: initialize steps and metrics here
        if shard_start is None and last_processed_id == 0:
            _check_and_queue_if_blocked(db, job_id, db_log, self.retry)
            _enforce_storage_limit(db, job_id, db_log)

            _ensure_steps_generic(job_id, ["avatar_sync"])
            step_id = _get_step_id(job_id, "avatar_sync")
            JobsController.update_step_progress(db, step_id, 0.0, "running")
            _update_action(step_id, "Starting avatar sync (CDN fetch mode)...")

            db_log(
                "Starting Avatar Sync — CDN Fetch Mode (smart filtering enabled)",
                level="INFO",
                step="avatar_sync",
            )

            # Count total eligible users for progress tracking
            total_eligible = (
                db.query(sqla_func.count(UserMetadata.id))
                .filter(
                    UserMetadata.remote_avatar_url.isnot(None),
                    UserMetadata.profile_key.isnot(None),
                )
                .scalar()
            ) or 0

            job.metrics = job.metrics or {}
            job.metrics.update({
                "total_eligible": total_eligible,
                "total_checked": 0,
                "unchanged": 0,
                "changed": 0,
                "new": 0,
                "missing": 0,
                "errors": 0,
                "batches_processed": 0,
                "shard_count": 1,
                "shards_completed": 0,
            })
            job.started_at = job.started_at or datetime.now(timezone.utc)
            flag_modified(job, "metrics")
            db.commit()

        # --- Read dynamic settings from DB (admin UI) per batch ---
        _cdn_timeout = _get_setting_int(db, "AVATAR_SYNC_CDN_TIMEOUT", settings.AVATAR_SYNC_CDN_TIMEOUT)
        _ssim_threshold = _get_setting_float(db, "AVATAR_SYNC_SSIM_THRESHOLD", settings.AVATAR_SYNC_SSIM_THRESHOLD)
        _batch_delay = _get_setting_int(db, "AVATAR_SYNC_BATCH_DELAY_SECONDS", settings.AVATAR_SYNC_BATCH_DELAY_SECONDS)
        _max_retries = _get_setting_int(db, "AVATAR_SYNC_MAX_RETRIES", settings.AVATAR_SYNC_MAX_RETRIES)

        # --- Alert threshold check ---
        should_alert, elapsed = check_alert_threshold(job.started_at)
        if should_alert:
            alert_key = "alert_logged"
            if not (job.metrics or {}).get(alert_key):
                db_log(
                    f"WARNING: Avatar sync has been running for {elapsed:.0f}s, "
                    f"exceeds alert threshold of {settings.AVATAR_SYNC_ALERT_IF_EXCEEDS_SECONDS}s",
                    level="WARNING",
                    step="avatar_sync",
                )
                job.metrics = job.metrics or {}
                job.metrics[alert_key] = True
                flag_modified(job, "metrics")
                db.commit()

        # --- Smart filtering query with shard bounds ---
        batch = build_smart_filter_query(
            db, last_processed_id, shard_end=shard_end
        ).all()

        # No more users in this shard -> shard complete
        if not batch:
            # Lock the job row for atomic shard completion tracking
            job = (
                db.query(IngestionJob)
                .filter(IngestionJob.id == job_id)
                .with_for_update()
                .one()
            )

            job.metrics = job.metrics or {}
            job.metrics["shards_completed"] = job.metrics.get("shards_completed", 0) + 1
            shard_count = job.metrics.get("shard_count", 1)
            all_done = job.metrics["shards_completed"] >= shard_count
            flag_modified(job, "metrics")

            if all_done:
                # Last shard to finish — mark job complete
                step_id = _get_step_id(job_id, "avatar_sync")
                JobsController.update_step_progress(db, step_id, 100.0, "completed")
                _update_action(step_id, "Complete")

                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)

                if job.started_at:
                    started = job.started_at
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    duration = (job.completed_at - started).total_seconds()
                    job.metrics["duration_seconds"] = round(duration, 1)
                    flag_modified(job, "metrics")

                db.commit()

                metrics_summary = job.metrics or {}
                db_log(
                    f"Avatar Sync completed. "
                    f"Checked: {metrics_summary.get('total_checked', 0)}, "
                    f"Changed: {metrics_summary.get('changed', 0)}, "
                    f"New: {metrics_summary.get('new', 0)}, "
                    f"Missing: {metrics_summary.get('missing', 0)}, "
                    f"Errors: {metrics_summary.get('errors', 0)}, "
                    f"Batches: {metrics_summary.get('batches_processed', 0)}, "
                    f"Duration: {metrics_summary.get('duration_seconds', 0)}s",
                    level="INFO",
                    step="avatar_sync",
                )
                return metrics_summary
            else:
                db.commit()
                db_log(
                    f"Shard completed ({job.metrics['shards_completed']}/{shard_count})",
                    level="INFO",
                    step="avatar_sync",
                )
                return None

        # --- Prepare data for thread-safe parallel fetch ---
        step_id = _get_step_id(job_id, "avatar_sync")
        batch_stats = {
            "checked": 0,
            "unchanged": 0,
            "changed": 0,
            "new": 0,
            "missing": 0,
            "errors": 0,
        }

        _update_action(
            step_id,
            f"Fetching batch from CDN (IDs > {last_processed_id}, size={len(batch)})...",
        )

        # Extract plain dicts for thread safety, keep ORM lookup for DB phase
        fetch_inputs = []
        orm_lookup = {}

        for user_meta, existing_avatar in batch:
            user_dict = {
                "id": user_meta.id,
                "service_id": user_meta.service_id,
                "remote_avatar_url": user_meta.remote_avatar_url,
                "profile_key": user_meta.profile_key,
            }
            avatar_dict = None
            if existing_avatar:
                avatar_dict = {
                    "id": existing_avatar.id,
                    "snapshot_hash": existing_avatar.snapshot_hash,
                    "s3_key": existing_avatar.s3_key,
                    "s3_url": existing_avatar.s3_url,
                    "file_size": existing_avatar.file_size,
                }
            fetch_inputs.append((user_dict, avatar_dict))
            orm_lookup[user_meta.id] = (user_meta, existing_avatar)

        # --- Submit to thread pool for parallel fetch + decrypt + S3 ---
        futures = {
            _fetch_pool.submit(_fetch_and_decrypt, u, a, _cdn_session, _cdn_timeout, _ssim_threshold): u
            for u, a in fetch_inputs
        }

        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                user_dict = futures[future]
                results.append({
                    "status": "error",
                    "user_info": user_dict,
                    "avatar_info": None,
                    "failure_reason": f"UNEXPECTED: {str(e)[:80]}",
                    "error_detail": f"Unexpected error for user {user_dict['service_id']}: {str(e)[:200]}",
                    "decrypted": None,
                    "new_hash": None,
                    "s3_key": None,
                    "s3_url": None,
                    "old_s3_key_deleted": False,
                    "file_size": None,
                    "ext": None,
                })
                logger.warning(
                    f"Avatar sync error for user {user_dict['service_id']}: {e}"
                )

        # --- Apply all DB changes in one transaction ---
        _apply_results_to_db(db, results, job_id, batch_stats, db_log, orm_lookup)

        # --- Update job metrics + step progress with row-level lock ---
        job = (
            db.query(IngestionJob)
            .filter(IngestionJob.id == job_id)
            .with_for_update()
            .one()
        )
        job.metrics = job.metrics or {}
        job.metrics["total_checked"] = job.metrics.get("total_checked", 0) + batch_stats["checked"]
        job.metrics["unchanged"] = job.metrics.get("unchanged", 0) + batch_stats["unchanged"]
        job.metrics["changed"] = job.metrics.get("changed", 0) + batch_stats["changed"]
        job.metrics["new"] = job.metrics.get("new", 0) + batch_stats["new"]
        job.metrics["missing"] = job.metrics.get("missing", 0) + batch_stats["missing"]
        job.metrics["errors"] = job.metrics.get("errors", 0) + batch_stats["errors"]
        job.metrics["batches_processed"] = job.metrics.get("batches_processed", 0) + 1
        flag_modified(job, "metrics")

        # Update step progress bar based on checked / total_eligible
        total_eligible = job.metrics.get("total_eligible", 0)
        total_checked = job.metrics["total_checked"]
        if total_eligible > 0:
            progress = min(99.0, (total_checked / total_eligible) * 100)
        else:
            progress = 50.0  # fallback if count unknown
        JobsController.update_step_progress(db, step_id, round(progress, 1), "running")
        _update_action(
            step_id,
            f"Processing: {total_checked}/{total_eligible} users "
            f"({batch_stats['changed']} changed, {batch_stats['errors']} errors this batch)",
        )

        db.commit()

        # Log batch summary — use ERROR level if there are failures so
        # the UI error dropdown filter shows them
        batch_log_level = "ERROR" if batch_stats["errors"] > 0 else "INFO"
        db_log(
            f"Batch {job.metrics['batches_processed']}: "
            f"{batch_stats['checked']} checked, "
            f"{batch_stats['changed']} changed, "
            f"{batch_stats['new']} new, "
            f"{batch_stats['unchanged']} unchanged, "
            f"{batch_stats['missing']} missing, "
            f"{batch_stats['errors']} errors",
            level=batch_log_level,
            step="avatar_sync",
        )

        # Re-queue for next batch with delay (cooperative multitasking)
        # Cursor is the last UserMetadata.id in the batch
        new_cursor = batch[-1][0].id
        run_avatar_sync_batch.apply_async(
            args=[job_id, new_cursor],
            kwargs={"shard_end": shard_end},
            queue="avatars",
            countdown=_batch_delay,
        )

        return None

    except Retry:
        # Let Celery handle the retry (FIFO queueing)
        raise
    except Exception as e:
        db_log(f"Avatar sync batch failed: {str(e)}", level="ERROR", step="avatar_sync")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()
