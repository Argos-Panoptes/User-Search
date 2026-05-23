"""
Signal Avatar Worker

Celery tasks for fetching, decrypting, and storing Signal user avatars.
- Downloads encrypted avatars from Signal CDN
- Decrypts using AES-256-GCM with user's profileKey
- Deduplicates via SHA256 hash
- Uploads to MinIO and links to User record
- Tracks batch progress via Redis counters and DB batch run records
"""

import logging
import threading
import os
import base64
import asyncio
import hashlib
import random
import uuid
from collections import defaultdict
from io import BytesIO
from datetime import datetime, timedelta

import aiohttp
import httpx
if sys.platform != "win32":
    import uvloop
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.orm import Session

from app.background_workers.celery_app import celery_app
from app.db.session import SessionLocal, s3_client
from app.db.schemas.models import User, IngestionJob, IngestionStep, IngestionLog, IngestionType
from app.db.schemas.media_models import File
from app.db.schemas.signal_avatar_models import SignalUserMetadata
from app.core.config import settings

logger = logging.getLogger(__name__)
if sys.platform != "win32":
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# =============================================================================
# AVATAR SYNC CONFIGURATION
# Tune these values based on your server capacity and CDN behaviour.
# You do not need to touch any other part of the file to adjust performance.
# =============================================================================

# Maximum number of concurrent CDN requests per batch run.
# Raise if error rate is below 5% and you want more speed.
# Lower if you see 429s increasing or server CPU/RAM spikes.
# Safe range: 20 (conservative) -> 150 (aggressive). Default: 50.
CONCURRENCY = 50

# Number of users processed in a single batch chunk.
# Larger = fewer DB round trips but more RAM per worker.
# Smaller = more granular progress reporting.
# Safe range: 100 -> 1000. Default: 500.
BATCH_CHUNK_SIZE = 500

# Maximum number of retry attempts per avatar on retryable errors (5xx, network).
# Does not apply to 403/404 which are skipped immediately with zero retries.
MAX_RETRIES = 3

# Base delay in seconds for exponential backoff on 5xx errors.
# Actual delay = BASE_RETRY_DELAY * (2 ** attempt) + jitter.
# Default: 1.0 second.
BASE_RETRY_DELAY = 1.0

# Hard ceiling on backoff wait time in seconds regardless of attempt count.
# Prevents workers from stalling indefinitely on persistent failures.
# Default: 30 seconds.
MAX_RETRY_DELAY = 30.0

# Maximum wait in seconds when CDN returns 429 and no Retry-After header.
# If Retry-After header is present it always takes priority over this value.
# Default: 30 seconds.
MAX_RATE_LIMIT_WAIT = 30.0

# How often to emit progress updates to the job log and Redis SSE stream.
# Higher = less logging overhead on large batches. Lower = more granular UI updates.
# Default: every 50 completions.
PROGRESS_REPORT_EVERY = 50

# MinIO/S3 storage path prefix for avatar files.
# Change this if you want avatars stored under a different bucket path.
AVATAR_STORAGE_PREFIX = "avatars/signal"

# aiohttp TCP connector settings.
# CONNECTOR_LIMIT: total connection pool size across all hosts. Should be >= CONCURRENCY.
# DNS_CACHE_TTL: seconds to cache DNS lookups. Reduces DNS overhead on repeated CDN calls.
CONNECTOR_LIMIT = 120
DNS_CACHE_TTL = 300

# How many seconds before an individual CDN request is considered timed out.
# Raise if you are seeing spurious timeout errors on slow connections.
# Lower if you want failed requests to fail fast and move on.
CDN_REQUEST_TIMEOUT = 15.0

# Maximum age in hours before an avatar is considered stale and eligible for re-fetch.
# This is the default used when no override is passed to the batch task.
DEFAULT_MAX_AGE_HOURS = 24
# =============================================================================

# Signal CDN base URL
SIGNAL_CDN_BASE_URL = "https://cdn.signal.org/"

# Redis keys for avatar settings
REDIS_AVATAR_AUTO_REFRESH_KEY = "signal_avatar:auto_refresh_enabled"
REDIS_AVATAR_INTERVAL_KEY = "signal_avatar:auto_refresh_interval_hours"
REDIS_AVATAR_BATCH_PREFIX = "avatar_batch"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _check_if_unencrypted(data: bytes):
    """Check if data is already an unencrypted image (magic bytes)."""
    if data[:3] == b'\xff\xd8\xff':
        return True, "jpg"
    if data[:4] == b'\x89PNG':
        return True, "png"
    if data[:4] == b'RIFF' and b'WEBP' in data[:12]:
        return True, "webp"
    if data[:4] == b'GIF8':
        return True, "gif"
    return False, None


def _detect_image_type(data: bytes):
    """Detect image type from magic bytes. Returns (extension, mime_type)."""
    if data[:3] == b'\xff\xd8\xff':
        return "jpg", "image/jpeg"
    if data[:4] == b'\x89PNG':
        return "png", "image/png"
    if data[:4] == b'RIFF' and b'WEBP' in data[:12]:
        return "webp", "image/webp"
    if data[:4] == b'GIF8':
        return "gif", "image/gif"
    return "jpg", "image/jpeg"  # Default fallback


def _decrypt_signal_avatar(encrypted_data: bytes, profile_key_b64: str) -> bytes | None:
    """
    Decrypt a Signal avatar using AES-256-GCM.

    Signal format: first 12 bytes = nonce/IV, remaining = ciphertext + GCM tag.
    Key is the profileKey decoded from base64 (32 bytes, used directly).
    """
    NONCE_LENGTH = 12
    GCM_TAG_LENGTH = 16

    if len(encrypted_data) < NONCE_LENGTH + GCM_TAG_LENGTH:
        return None

    # Check if already unencrypted
    is_image, _ = _check_if_unencrypted(encrypted_data)
    if is_image:
        return encrypted_data

    try:
        key = base64.b64decode(profile_key_b64)
        if len(key) != 32:
            logger.warning(f"Invalid profile key length: {len(key)} (expected 32)")
            return None

        nonce = encrypted_data[:NONCE_LENGTH]
        ciphertext_with_tag = encrypted_data[NONCE_LENGTH:]

        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(nonce, ciphertext_with_tag, None)

        # Verify result looks like an image
        is_image, _ = _check_if_unencrypted(decrypted)
        if is_image:
            return decrypted

        logger.warning("Decrypted data doesn't look like an image")
        return None

    except Exception as e:
        logger.warning(f"Avatar decryption failed: {e}")
        return None


def _get_redis_sync():
    """Get synchronous Redis client."""
    import redis as sync_redis
    return sync_redis.from_url(settings.REDIS_URL, decode_responses=True)


def _increment_batch_counter(batch_id: str, field: str, amount: int = 1):
    """Increment a Redis counter for batch progress tracking."""
    if not batch_id:
        return
    try:
        r = _get_redis_sync()
        key = f"{REDIS_AVATAR_BATCH_PREFIX}:{batch_id}:{field}"
        r.incrby(key, amount)
        r.expire(key, 86400)  # 24h TTL
    except Exception:
        pass


def _get_batch_counters(batch_id: str) -> dict:
    """Read all Redis counters for a batch."""
    try:
        r = _get_redis_sync()
        prefix = f"{REDIS_AVATAR_BATCH_PREFIX}:{batch_id}"
        return {
            "succeeded": int(r.get(f"{prefix}:succeeded") or 0),
            "failed": int(r.get(f"{prefix}:failed") or 0),
            "real_errors": int(r.get(f"{prefix}:real_errors") or r.get(f"{prefix}:failed") or 0),
            "dead_urls": int(r.get(f"{prefix}:dead_urls") or 0),
            "skipped": int(r.get(f"{prefix}:skipped") or 0),
            "new_avatars": int(r.get(f"{prefix}:new_avatars") or 0),
            "unchanged": int(r.get(f"{prefix}:unchanged") or 0),
            "processed": int(r.get(f"{prefix}:processed") or 0),
        }
    except Exception:
        return {}


def is_avatar_auto_refresh_enabled() -> bool:
    """Check if avatar auto-refresh is enabled via Redis."""
    try:
        r = _get_redis_sync()
        val = r.get(REDIS_AVATAR_AUTO_REFRESH_KEY)
        return val == "1"
    except Exception:
        return False


def set_avatar_auto_refresh(enabled: bool):
    """Set avatar auto-refresh toggle in Redis."""
    r = _get_redis_sync()
    r.set(REDIS_AVATAR_AUTO_REFRESH_KEY, "1" if enabled else "0")


def get_avatar_refresh_interval_hours() -> int:
    """Get the auto-refresh interval in hours from Redis."""
    try:
        r = _get_redis_sync()
        val = r.get(REDIS_AVATAR_INTERVAL_KEY)
        return int(val) if val else DEFAULT_MAX_AGE_HOURS
    except Exception:
        return DEFAULT_MAX_AGE_HOURS


def set_avatar_refresh_interval_hours(hours: int):
    """Set the auto-refresh interval in Redis."""
    r = _get_redis_sync()
    r.set(REDIS_AVATAR_INTERVAL_KEY, str(hours))


def _publish_redis(channel: str, data: dict):
    """Publish event to Redis for SSE streaming. Fire-and-forget."""
    try:
        import json
        import redis as sync_redis
        r = sync_redis.from_url(settings.REDIS_URL)
        r.publish(channel, json.dumps(data))
        r.close()
    except Exception:
        pass


def _log_to_job(db, job_id: int, message: str, level: str = "INFO", step_name: str = None):
    """Write a log entry to ingestion_logs and publish to Redis for SSE."""
    try:
        log = IngestionLog(job_id=job_id, message=message, log_level=level, step_name=step_name)
        db.add(log)
        db.commit()

        _publish_redis(f"log:{job_id}", {
            "timestamp": log.timestamp.isoformat() if log.timestamp else datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "step_name": step_name,
        })
    except Exception:
        db.rollback()


def _update_step(db, job_id: int, step_name: str, status: str, progress: float = None, details: dict = None):
    """Update an IngestionStep's status/progress and publish to Redis for SSE."""
    step = db.query(IngestionStep).filter(
        IngestionStep.job_id == job_id,
        IngestionStep.step_name == step_name,
    ).first()
    if step:
        step.status = status
        if progress is not None:
            step.progress_percentage = progress
        if details:
            step.details = {**(step.details or {}), **details}
        if status == "running" and not step.started_at:
            step.started_at = datetime.utcnow()
        if status in ("completed", "failed"):
            step.completed_at = datetime.utcnow()
        db.commit()

        _publish_redis(f"progress:{job_id}", {
            "step_name": step.step_name,
            "status": step.status,
            "progress_percentage": step.progress_percentage,
            "details": step.details,
            "started_at": step.started_at.isoformat() if step.started_at else None,
            "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        })


# ---------------------------------------------------------------------------
# Celery Tasks
# ---------------------------------------------------------------------------

@celery_app.task(
    name="signal_avatar.fetch_single_avatar",
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=10,
    acks_late=True,
    reject_on_worker_lost=True,
)
def fetch_single_avatar_task(self, user_id: int, force_refresh: bool = False, batch_id: str = None):
    """
    Fetch, decrypt, and store a single user's avatar from Signal CDN.
    Reads profile_key/remote_avatar_url from signal_user_metadata (via signal_uuid).
    Logs detailed results to IngestionLog for real-time UI feedback.
    """
    db: Session = SessionLocal()
    job_id = int(batch_id) if batch_id else None
    display_name = f"user {user_id}"

    def _done(status_key, msg):
        """Helper to increment counter + log to job."""
        _increment_batch_counter(batch_id, status_key)
        _increment_batch_counter(batch_id, "processed")
        if job_id:
            level = "ERROR" if status_key == "failed" else "WARNING" if status_key == "skipped" else "INFO"
            _log_to_job(db, job_id, f"[{display_name}] {msg}", level=level, step_name="fetch_avatars")

    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user or not user.signal_uuid:
            _done("failed", "User not found or no signal_uuid")
            return {"status": "error", "user_id": user_id}

        meta = db.query(SignalUserMetadata).filter(
            SignalUserMetadata.signal_uuid == user.signal_uuid
        ).first()
        if not meta or not meta.remote_avatar_url or not meta.profile_key:
            _done("skipped", "Missing avatar URL or profile key")
            return {"status": "skipped", "user_id": user_id}

        display_name = meta.profile_full_name or meta.profile_name or user.display_name or f"user {user_id}"

        # Build CDN URL
        avatar_path = meta.remote_avatar_url
        if not avatar_path.startswith("http"):
            if not avatar_path.startswith("profiles/"):
                avatar_path = f"profiles/{avatar_path}"
            cdn_url = f"{SIGNAL_CDN_BASE_URL}{avatar_path}"
        else:
            cdn_url = avatar_path

        # Download encrypted avatar (try without auth first, retry with access key on 403)
        try:
            with httpx.Client(timeout=CDN_REQUEST_TIMEOUT, verify=False) as client:
                response = client.get(cdn_url)
                if response.status_code == 403 and meta.access_key:
                    response = client.get(cdn_url, headers={
                        "Unidentified-Access-Key": meta.access_key,
                    })
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                meta.avatar_last_fetched_at = datetime.utcnow()
                db.commit()
                _done("skipped", f"CDN returned {e.response.status_code}")
                return {"status": "skipped", "user_id": user_id}
            _done("failed", f"CDN error: {e.response.status_code}")
            raise self.retry(exc=e)
        except Exception as e:
            _done("failed", f"Download failed: {e}")
            raise self.retry(exc=e)

        encrypted_data = response.content
        if not encrypted_data:
            meta.avatar_last_fetched_at = datetime.utcnow()
            db.commit()
            _done("skipped", "Empty response from CDN")
            return {"status": "skipped", "user_id": user_id}

        # Decrypt
        decrypted_data = _decrypt_signal_avatar(encrypted_data, meta.profile_key)
        if not decrypted_data:
            meta.avatar_last_fetched_at = datetime.utcnow()
            db.commit()
            _done("failed", "Decryption failed")
            return {"status": "failed", "user_id": user_id}

        # SHA256 deduplication
        sha256_hash = hashlib.sha256(decrypted_data).hexdigest()

        # Check if already has this exact avatar
        if not force_refresh and meta.avatar_file_id:
            existing_avatar = db.query(File).filter(File.file_id == meta.avatar_file_id).first()
            if existing_avatar and existing_avatar.sha256 == sha256_hash:
                meta.avatar_last_fetched_at = datetime.utcnow()
                db.commit()
                _increment_batch_counter(batch_id, "unchanged")
                _increment_batch_counter(batch_id, "succeeded")
                _increment_batch_counter(batch_id, "processed")
                # Don't log unchanged (too noisy)
                return {"status": "unchanged", "user_id": user_id, "file_id": meta.avatar_file_id}

        # Check if file with this SHA256 already exists globally
        existing_file = db.query(File).filter(File.sha256 == sha256_hash).first()
        if existing_file:
            file_id = existing_file.file_id
        else:
            # Upload to MinIO
            ext, mime_type = _detect_image_type(decrypted_data)
            filename = f"{sha256_hash[:12]}.{ext}"
            object_key = f"{AVATAR_STORAGE_PREFIX}/{user_id}/{filename}"

            try:
                s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME, Key=object_key,
                    Body=BytesIO(decrypted_data), ContentType=mime_type,
                )
            except Exception as e:
                _done("failed", f"Upload to storage failed: {e}")
                raise self.retry(exc=e)

            file_record = File(
                object_key=object_key, sha256=sha256_hash,
                filename=filename, mime=mime_type, size=len(decrypted_data),
            )
            db.add(file_record)
            db.flush()
            file_id = file_record.file_id

        # Update signal_user_metadata only (single source of truth)
        meta.avatar_file_id = file_id
        meta.avatar_last_fetched_at = datetime.utcnow()
        db.commit()

        _increment_batch_counter(batch_id, "succeeded")
        _increment_batch_counter(batch_id, "new_avatars")
        _increment_batch_counter(batch_id, "processed")
        if job_id:
            _log_to_job(db, job_id, f"[{display_name}] Saved avatar (file_id={file_id}, {len(decrypted_data)} bytes)", step_name="fetch_avatars")
        return {"status": "success", "user_id": user_id, "file_id": file_id}

    except Exception as e:
        db.rollback()
        logger.error(f"Error fetching avatar for user {user_id}: {e}", exc_info=True)
        _increment_batch_counter(batch_id, "failed")
        _increment_batch_counter(batch_id, "processed")
        if job_id:
            _log_to_job(db, job_id, f"[{display_name}] Error: {e}", level="ERROR", step_name="fetch_avatars")
        raise

    finally:
        db.close()


@celery_app.task(name="signal_avatar.orchestrate_bulk_refresh")
def orchestrate_bulk_refresh_task(
    job_id: int,
    batch_size: int = BATCH_CHUNK_SIZE,
    force_refresh: bool = False,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
):
    """
    Bulk avatar refresh — fetches all eligible avatars concurrently using
    asyncio + aiohttp with a shared session and conservative semaphore limiting.
    Tracks progress via IngestionJob/Step/Log with real-time SSE updates.
    """
    from sqlalchemy import or_

    db = SessionLocal()
    try:
        # Mark job running
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = "running"
            job.started_at = datetime.utcnow()
            db.commit()

        # --- Step 1: Find eligible users ---
        _update_step(db, job_id, "find_eligible", "running")
        _log_to_job(db, job_id, "Finding eligible users for avatar refresh...", step_name="find_eligible")

        age_cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        query = (
            db.query(User.user_id, User.display_name, User.signal_uuid,
                     SignalUserMetadata.id.label("meta_id"),
                     SignalUserMetadata.remote_avatar_url,
                     SignalUserMetadata.profile_key,
                     SignalUserMetadata.access_key,
                     SignalUserMetadata.avatar_file_id,
                     SignalUserMetadata.avatar_last_fetched_at,
                     SignalUserMetadata.profile_full_name,
                     SignalUserMetadata.profile_name)
            .join(SignalUserMetadata, User.signal_uuid == SignalUserMetadata.signal_uuid)
            .filter(
                SignalUserMetadata.remote_avatar_url.isnot(None),
                SignalUserMetadata.profile_key.isnot(None),
            )
        )
        if not force_refresh:
            query = query.filter(
                or_(
                    SignalUserMetadata.avatar_last_fetched_at.is_(None),
                    SignalUserMetadata.avatar_last_fetched_at < age_cutoff,
                )
            )

        eligible = query.all()
        total = len(eligible)

        _log_to_job(db, job_id, f"Found {total} eligible users (force={force_refresh}, max_age={max_age_hours}h)", step_name="find_eligible")
        _update_step(db, job_id, "find_eligible", "completed", progress=100.0, details={
            "total_eligible": total, "force_refresh": force_refresh,
        })

        if total == 0:
            _log_to_job(db, job_id, "No eligible users found, completing job")
            _update_step(db, job_id, "fetch_avatars", "completed", progress=100.0)
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                db.commit()
            _publish_redis(f"progress:{job_id}", {"step_name": "_job", "status": "completed"})
            return {"job_id": job_id, "total_users": 0}

        # --- Step 2: Fetch avatars concurrently ---
        _update_step(db, job_id, "fetch_avatars", "running", progress=0.0, details={
            "description": "Fetch & decrypt avatars from CDN",
            "substeps": ["Starting..."],
            "total_users": total, "succeeded": 0, "real_errors": 0, "dead_urls": 0, "skipped": 0,
            "new_avatars": 0, "unchanged": 0, "processed": 0,
        })

        counters = {
            "succeeded": 0,
            "failed": 0,
            "real_errors": 0,
            "dead_urls": 0,
            "skipped": 0,
            "new_avatars": 0,
            "unchanged": 0,
            "processed": 0,
        }

        # ---------------------------------------------------------------
        # Pre-build hash maps: O(n) build, O(1) per-avatar lookup
        # ---------------------------------------------------------------
        # Map 1: file_id → sha256 for current-avatar unchanged check
        avatar_file_ids = {r.avatar_file_id for r in eligible if r.avatar_file_id}
        fileid_to_sha = {}  # file_id → sha256
        if avatar_file_ids:
            for f in db.query(File.file_id, File.sha256).filter(File.file_id.in_(avatar_file_ids)).all():
                fileid_to_sha[f.file_id] = f.sha256

        # Map 2: sha256 → file_id for global dedup
        sha_to_fileid = {}  # sha256 → file_id
        for f in db.query(File.sha256, File.file_id).all():
            sha_to_fileid[f.sha256] = f.file_id

        # ---------------------------------------------------------------
        # URL-level dedup: group users by remote_avatar_url so each
        # unique CDN URL is fetched exactly once, result fanned out.
        # Reduces CDN fetches from N → unique(N).
        # ---------------------------------------------------------------
        # Convert eligible rows to plain dicts for thread safety
        user_dicts = []
        for r in eligible:
            user_dicts.append({
                "user_id": r.user_id,
                "meta_id": r.meta_id,
                "display_name": r.profile_full_name or r.profile_name or r.display_name or f"user {r.user_id}",
                "remote_avatar_url": r.remote_avatar_url,
                "profile_key": r.profile_key,
                "access_key": r.access_key,
                "avatar_file_id": r.avatar_file_id,
                "avatar_last_fetched_at": r.avatar_last_fetched_at,
            })

        never_fetched_count = sum(1 for r in user_dicts if r["avatar_last_fetched_at"] is None)
        recheck_count = total - never_fetched_count

        url_groups = defaultdict(list)  # cdn_url → [user_info, ...]
        for ud in user_dicts:
            avatar_path = ud["remote_avatar_url"]
            if not avatar_path.startswith("http"):
                if not avatar_path.startswith("profiles/"):
                    avatar_path = f"profiles/{avatar_path}"
                cdn_url = f"{SIGNAL_CDN_BASE_URL}{avatar_path}"
            else:
                cdn_url = avatar_path
            ud["_cdn_url"] = cdn_url
            url_groups[cdn_url].append(ud)

        unique_urls = len(url_groups)
        _log_to_job(db, job_id,
            f"Fetching {total} avatars ({unique_urls} unique CDN URLs) with {CONCURRENCY} concurrent workers...",
            step_name="fetch_avatars")
        _log_to_job(
            db,
            job_id,
            (
                f"Batch workload: {never_fetched_count} never fetched, "
                f"{recheck_count} re-checks"
            ),
            step_name="fetch_avatars",
        )

        # ---------------------------------------------------------------
        # Execute with shared aiohttp session + asyncio concurrency controls
        # ---------------------------------------------------------------
        def _build_progress_details(current_counters: dict) -> dict:
            processed = current_counters["processed"]
            return {
                "description": "Fetch & decrypt avatars from CDN",
                "substeps": [
                    f"Downloaded: {current_counters['succeeded']} ({current_counters['new_avatars']} new, {current_counters['unchanged']} unchanged)",
                    f"Skipped: {current_counters['dead_urls']} dead URLs (403/404)",
                    f"Real errors: {current_counters['real_errors']}",
                    f"Processed: {processed} / {total}",
                ],
                **current_counters,
                "total_users": total,
                "unique_urls": unique_urls,
                "concurrency": CONCURRENCY,
                "never_fetched": never_fetched_count,
                "rechecks": recheck_count,
            }

        async def _sleep_for_status(status_code: int, attempt: int, response_headers=None, prev_delay: float = BASE_RETRY_DELAY) -> float:
            if status_code == 429:
                retry_after = None
                if response_headers:
                    retry_after = response_headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        delay = min(MAX_RATE_LIMIT_WAIT, max(0.0, float(retry_after)))
                    except (TypeError, ValueError):
                        delay = min(MAX_RATE_LIMIT_WAIT, random.uniform(1.0, max(1.0, prev_delay * 3)))
                else:
                    delay = min(MAX_RATE_LIMIT_WAIT, random.uniform(1.0, max(1.0, prev_delay * 3)))
            else:
                delay = min(MAX_RETRY_DELAY, BASE_RETRY_DELAY * (2 ** attempt) + random.uniform(0.0, 1.0))

            await asyncio.sleep(delay)
            return delay

        async def _fetch_one(
            group_users,
            session,
            semaphore,
            sha256_to_file_id,
            file_id_to_sha256,
            inflight_shas,
            inflight_waiters,
            inflight_lock,
        ):
            try:
                results = []
                first = group_users[0]
                cdn_url = first["_cdn_url"]
                prev_delay = BASE_RETRY_DELAY

                async with semaphore:
                    response_data = None
                    response_status = None

                    for attempt in range(MAX_RETRIES + 1):
                        try:
                            async with session.get(cdn_url) as resp:
                                response_status = resp.status
                                if resp.status == 403 and first.get("access_key"):
                                    await resp.read()
                                    async with session.get(
                                        cdn_url,
                                        headers={"Unidentified-Access-Key": first["access_key"]},
                                    ) as retry_resp:
                                        response_status = retry_resp.status
                                        if retry_resp.status in (403, 404):
                                            for ui in group_users:
                                                results.append({
                                                    "status": "skipped",
                                                    "name": ui["display_name"],
                                                    "msg": f"CDN {retry_resp.status}",
                                                    "meta_id": ui["meta_id"],
                                                    "user_id": ui["user_id"],
                                                    "dead_url": True,
                                                    "counter_deltas": {"dead_urls": 1, "skipped": 1, "processed": 1},
                                                })
                                            return results
                                        if retry_resp.status == 429 or retry_resp.status >= 500:
                                            if attempt >= MAX_RETRIES:
                                                break
                                            prev_delay = await _sleep_for_status(
                                                retry_resp.status,
                                                attempt,
                                                response_headers=retry_resp.headers,
                                                prev_delay=prev_delay,
                                            )
                                            continue
                                        if retry_resp.status >= 400:
                                            for ui in group_users:
                                                results.append({
                                                    "status": "failed",
                                                    "name": ui["display_name"],
                                                    "msg": f"CDN {retry_resp.status}",
                                                    "meta_id": ui["meta_id"],
                                                    "user_id": ui["user_id"],
                                                    "counter_deltas": {"failed": 1, "real_errors": 1, "processed": 1},
                                                })
                                            return results
                                        response_data = await retry_resp.read()
                                        break

                                if resp.status in (403, 404):
                                    for ui in group_users:
                                        results.append({
                                            "status": "skipped",
                                            "name": ui["display_name"],
                                            "msg": f"CDN {resp.status}",
                                            "meta_id": ui["meta_id"],
                                            "user_id": ui["user_id"],
                                            "dead_url": True,
                                            "counter_deltas": {"dead_urls": 1, "skipped": 1, "processed": 1},
                                        })
                                    return results
                                if resp.status == 429 or resp.status >= 500:
                                    if attempt >= MAX_RETRIES:
                                        break
                                    prev_delay = await _sleep_for_status(
                                        resp.status,
                                        attempt,
                                        response_headers=resp.headers,
                                        prev_delay=prev_delay,
                                    )
                                    continue
                                if resp.status >= 400:
                                    for ui in group_users:
                                        results.append({
                                            "status": "failed",
                                            "name": ui["display_name"],
                                            "msg": f"CDN {resp.status}",
                                            "meta_id": ui["meta_id"],
                                            "user_id": ui["user_id"],
                                            "counter_deltas": {"failed": 1, "real_errors": 1, "processed": 1},
                                        })
                                    return results

                                response_data = await resp.read()
                                break
                        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                            if attempt >= MAX_RETRIES:
                                for ui in group_users:
                                    results.append({
                                        "status": "failed",
                                        "name": ui["display_name"],
                                        "msg": str(exc),
                                        "meta_id": ui["meta_id"],
                                        "user_id": ui["user_id"],
                                        "counter_deltas": {"failed": 1, "real_errors": 1, "processed": 1},
                                    })
                                return results
                            prev_delay = await _sleep_for_status(500, attempt, prev_delay=prev_delay)

                    if response_data is None:
                        final_status = response_status or 500
                        for ui in group_users:
                            results.append({
                                "status": "failed",
                                "name": ui["display_name"],
                                "msg": f"CDN {final_status}",
                                "meta_id": ui["meta_id"],
                                "user_id": ui["user_id"],
                                "counter_deltas": {"failed": 1, "real_errors": 1, "processed": 1},
                            })
                        return results

                    if not response_data:
                        for ui in group_users:
                            results.append({
                                "status": "skipped",
                                "name": ui["display_name"],
                                "msg": "Empty response",
                                "meta_id": ui["meta_id"],
                                "user_id": ui["user_id"],
                                "counter_deltas": {"skipped": 1, "processed": 1},
                            })
                        return results

                    decrypted = _decrypt_signal_avatar(response_data, first["profile_key"])
                    if not decrypted:
                        for ui in group_users:
                            dec = _decrypt_signal_avatar(response_data, ui["profile_key"])
                            if dec:
                                decrypted = dec
                                break
                        if not decrypted:
                            for ui in group_users:
                                results.append({
                                    "status": "failed",
                                    "name": ui["display_name"],
                                    "msg": "Decryption failed",
                                    "meta_id": ui["meta_id"],
                                    "user_id": ui["user_id"],
                                    "counter_deltas": {"failed": 1, "real_errors": 1, "processed": 1},
                                })
                            return results

                    sha = hashlib.sha256(decrypted).hexdigest()
                    shared_upload_result = None

                    for ui in group_users:
                        existing_sha = file_id_to_sha256.get(ui["avatar_file_id"]) if ui["avatar_file_id"] else None
                        if not force_refresh and existing_sha == sha:
                            results.append({
                                "status": "unchanged",
                                "name": ui["display_name"],
                                "msg": "Same avatar",
                                "meta_id": ui["meta_id"],
                                "user_id": ui["user_id"],
                                "counter_deltas": {"succeeded": 1, "unchanged": 1, "processed": 1},
                            })
                            continue

                        existing_file_id = sha256_to_file_id.get(sha)
                        if existing_file_id:
                            results.append({
                                "status": "success",
                                "name": ui["display_name"],
                                "msg": f"Saved (file_id={existing_file_id}, {len(decrypted)}B, dedup)",
                                "file_id": existing_file_id,
                                "meta_id": ui["meta_id"],
                                "user_id": ui["user_id"],
                                "sha": sha,
                                "counter_deltas": {"succeeded": 1, "new_avatars": 1, "processed": 1},
                            })
                            continue

                        if shared_upload_result is None:
                            loop = asyncio.get_running_loop()
                            with inflight_lock:
                                if sha in inflight_shas:
                                    waiter = inflight_waiters[sha]
                                    is_owner = False
                                else:
                                    inflight_shas.add(sha)
                                    waiter = loop.create_future()
                                    inflight_waiters[sha] = waiter
                                    is_owner = True

                            if is_owner:
                                try:
                                    ext, mime_type = _detect_image_type(decrypted)
                                    filename = f"{sha[:12]}.{ext}"
                                    obj_key = f"{AVATAR_STORAGE_PREFIX}/{ui['user_id']}/{filename}"
                                    s3_client.put_object(
                                        Bucket=settings.S3_BUCKET_NAME,
                                        Key=obj_key,
                                        Body=BytesIO(decrypted),
                                        ContentType=mime_type,
                                    )
                                    shared_upload_result = {
                                        "obj_key": obj_key,
                                        "filename": filename,
                                        "mime": mime_type,
                                        "size": len(decrypted),
                                    }
                                    waiter.set_result(shared_upload_result)
                                except Exception as exc:
                                    waiter.set_exception(exc)
                                    with inflight_lock:
                                        inflight_shas.discard(sha)
                                        inflight_waiters.pop(sha, None)
                                    results.append({
                                        "status": "failed",
                                        "name": ui["display_name"],
                                        "msg": f"Upload failed: {exc}",
                                        "meta_id": ui["meta_id"],
                                        "user_id": ui["user_id"],
                                        "counter_deltas": {"failed": 1, "real_errors": 1, "processed": 1},
                                    })
                                    continue
                                with inflight_lock:
                                    inflight_shas.discard(sha)
                                    inflight_waiters.pop(sha, None)
                            else:
                                try:
                                    shared_upload_result = await waiter
                                except Exception as exc:
                                    results.append({
                                        "status": "failed",
                                        "name": ui["display_name"],
                                        "msg": f"Upload failed: {exc}",
                                        "meta_id": ui["meta_id"],
                                        "user_id": ui["user_id"],
                                        "counter_deltas": {"failed": 1, "real_errors": 1, "processed": 1},
                                    })
                                    continue

                        results.append({
                            "status": "success",
                            "name": ui["display_name"],
                            "msg": f"Saved ({len(decrypted)}B)",
                            "meta_id": ui["meta_id"],
                            "user_id": ui["user_id"],
                            "sha": sha,
                            "new_file": True,
                            **shared_upload_result,
                            "counter_deltas": {"succeeded": 1, "new_avatars": 1, "processed": 1},
                        })

                return results
            except Exception as exc:
                return [{
                    "status": "failed",
                    "name": ui["display_name"],
                    "msg": str(exc),
                    "meta_id": ui["meta_id"],
                    "user_id": ui["user_id"],
                    "counter_deltas": {"failed": 1, "real_errors": 1, "processed": 1},
                } for ui in group_users]

        async def _run_fetches():
            timeout = aiohttp.ClientTimeout(total=CDN_REQUEST_TIMEOUT)
            connector = aiohttp.TCPConnector(
                limit=CONNECTOR_LIMIT,
                ttl_dns_cache=DNS_CACHE_TTL,
                ssl=False,
            )
            semaphore = asyncio.Semaphore(CONCURRENCY)
            inflight_lock = threading.Lock()
            inflight_shas = set()
            inflight_waiters = {}

            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                tasks = [
                    _fetch_one(
                        group,
                        session,
                        semaphore,
                        sha_to_fileid,
                        fileid_to_sha,
                        inflight_shas,
                        inflight_waiters,
                        inflight_lock,
                    )
                    for group in url_groups.values()
                ]
                return await asyncio.gather(*tasks, return_exceptions=True)

        all_results = []
        gathered_results = asyncio.run(_run_fetches())
        for group_result in gathered_results:
            if isinstance(group_result, Exception):
                logger.error("Unhandled avatar group fetch error: %s", group_result)
                continue
            all_results.extend(group_result)

        processed_since_report = 0
        for result in all_results:
            deltas = result.get("counter_deltas", {})
            for field, amount in deltas.items():
                counters[field] += amount

            processed_since_report += 1
            if processed_since_report >= PROGRESS_REPORT_EVERY:
                processed_since_report = 0
                pct = round(min(counters["processed"] / total * 100, 100), 1)
                _update_step(
                    db,
                    job_id,
                    "fetch_avatars",
                    "running",
                    progress=pct,
                    details=_build_progress_details(counters),
                )
                _log_to_job(
                    db,
                    job_id,
                    (
                        f"Processed {counters['processed']} / {total} avatars "
                        f"({counters['succeeded']} succeeded, {counters['dead_urls']} dead URLs, {counters['real_errors']} real errors)"
                    ),
                    step_name="fetch_avatars",
                )

        try:
            import redis as sync_redis

            redis_conn = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
            pipe = redis_conn.pipeline()
            prefix = f"{REDIS_AVATAR_BATCH_PREFIX}:{job_id}"
            for field, val in counters.items():
                pipe.set(f"{prefix}:{field}", val)
                pipe.expire(f"{prefix}:{field}", 86400)
            pipe.execute()
            redis_conn.close()
        except Exception:
            pass

        # ---------------------------------------------------------------
        # Bulk DB writes: batch File inserts + batch meta updates
        # ---------------------------------------------------------------
        now = datetime.utcnow()

        # 1. Bulk insert new File records
        new_file_records = []
        sha_to_new_file = {}  # sha → File ORM object (after flush)
        seen_new_shas = set()
        for r in all_results:
            if r.get("new_file") and r.get("sha") not in seen_new_shas:
                seen_new_shas.add(r["sha"])
                rec = File(
                    object_key=r["obj_key"], sha256=r["sha"],
                    filename=r["filename"], mime=r["mime"], size=r["size"],
                )
                new_file_records.append(rec)

        if new_file_records:
            db.bulk_save_objects(new_file_records, return_defaults=True)
            db.flush()
            # Build sha → file_id mapping from the flushed records
            for rec in new_file_records:
                sha_to_fileid[rec.sha256] = rec.file_id

        # 2. Batch meta updates: collect all meta_id → file_id + timestamp
        meta_updates_new = []       # meta_ids that need avatar_file_id + timestamp
        meta_updates_touch = []     # meta_ids that only need timestamp
        meta_updates_dead = []      # meta_ids that need remote_avatar_url cleared + timestamp
        for r in all_results:
            meta_id = r.get("meta_id")
            if not meta_id:
                continue
            status = r["status"]

            if status == "success":
                sha = r.get("sha")
                file_id = r.get("file_id") or sha_to_fileid.get(sha)
                if file_id:
                    meta_updates_new.append({"meta_id": meta_id, "file_id": file_id})
            elif status == "skipped" and r.get("dead_url"):
                meta_updates_dead.append(meta_id)
            elif status in ("unchanged", "skipped"):
                meta_updates_touch.append(meta_id)

        # Apply new avatar links
        if meta_updates_new:
            for batch_start in range(0, len(meta_updates_new), batch_size):
                batch_chunk = meta_updates_new[batch_start:batch_start + batch_size]
                ids_to_files = {m["meta_id"]: m["file_id"] for m in batch_chunk}
                metas = db.query(SignalUserMetadata).filter(
                    SignalUserMetadata.id.in_(ids_to_files.keys())
                ).all()
                for m in metas:
                    m.avatar_file_id = ids_to_files[m.id]
                    m.avatar_last_fetched_at = now

        # Apply timestamp-only updates
        if meta_updates_touch:
            for batch_start in range(0, len(meta_updates_touch), batch_size):
                batch_ids = meta_updates_touch[batch_start:batch_start + batch_size]
                metas = db.query(SignalUserMetadata).filter(
                    SignalUserMetadata.id.in_(batch_ids)
                ).all()
                for m in metas:
                    m.avatar_last_fetched_at = now

        # Retire dead CDN URLs so they stop re-entering the eligible pool.
        if meta_updates_dead:
            for batch_start in range(0, len(meta_updates_dead), batch_size):
                batch_ids = meta_updates_dead[batch_start:batch_start + batch_size]
                metas = db.query(SignalUserMetadata).filter(
                    SignalUserMetadata.id.in_(batch_ids)
                ).all()
                for m in metas:
                    m.remote_avatar_url = None
                    m.avatar_last_fetched_at = now

        db.commit()

        # --- Complete ---
        final_status = "failed" if counters["real_errors"] > 0 and counters["succeeded"] == 0 else "completed"

        _update_step(db, job_id, "fetch_avatars", "completed", progress=100.0, details={
            **_build_progress_details(counters),
            "substeps": [
                f"Downloaded: {counters['succeeded']} ({counters['new_avatars']} new, {counters['unchanged']} unchanged)",
                f"Skipped: {counters['dead_urls']} dead URLs (403/404)",
                f"Real errors: {counters['real_errors']}",
                f"Total: {total}",
            ],
        })

        _log_to_job(db, job_id,
            f"Refresh complete: {counters['succeeded']} succeeded ({counters['new_avatars']} new, "
            f"{counters['unchanged']} unchanged), {counters['dead_urls']} dead URLs skipped, "
            f"{counters['real_errors']} real errors",
            step_name="fetch_avatars")

        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = final_status
            job.completed_at = datetime.utcnow()
            db.commit()

        _publish_redis(f"progress:{job_id}", {"step_name": "_job", "status": final_status})

        # Sync avatars to OpenSearch if any new
        if counters["new_avatars"] > 0:
            sync_avatars_to_opensearch_task.apply_async(queue="io_bound")

        return {"job_id": job_id, "total_users": total, **counters}

    except Exception as e:
        logger.error(f"Avatar refresh job {job_id} failed: {e}", exc_info=True)
        try:
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
            _log_to_job(db, job_id, f"Refresh failed: {e}", level="ERROR")
            _publish_redis(f"progress:{job_id}", {"step_name": "_job", "status": "failed"})
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(name="signal_avatar.update_batch_run_stats")
def update_batch_run_stats_task():
    """
    Periodic task to update running avatar refresh jobs with Redis counter progress.
    Marks completed jobs as completed/failed.
    """
    db = SessionLocal()
    try:
        # Find running signal_avatar refresh jobs (those with a "fetch_avatars" step)
        ing_type = db.query(IngestionType).filter(IngestionType.name == "signal_avatar").first()
        if not ing_type:
            return {"status": "no_type"}

        running_jobs = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.ingestion_type_id == ing_type.id,
                IngestionJob.status == "running",
            )
            .all()
        )

        if not running_jobs:
            return {"status": "no_running_jobs"}

        for job in running_jobs:
            # Only process refresh jobs (have fetch_avatars step)
            fetch_step = db.query(IngestionStep).filter(
                IngestionStep.job_id == job.id,
                IngestionStep.step_name == "fetch_avatars",
            ).first()
            if not fetch_step:
                continue

            batch_id = str(job.id)
            counters = _get_batch_counters(batch_id)
            if not counters:
                continue

            total_users = (fetch_step.details or {}).get("total_users", 0)
            processed = counters.get("processed", 0)

            # Update step details with counter values
            new_details = {
                **(fetch_step.details or {}),
                "description": "Fetch & decrypt avatars from CDN",
                "substeps": [
                    f"Downloaded: {counters.get('succeeded', 0)} ({counters.get('new_avatars', 0)} new, {counters.get('unchanged', 0)} unchanged)",
                    f"Skipped: {counters.get('dead_urls', 0)} dead URLs (403/404)",
                    f"Real errors: {counters.get('real_errors', counters.get('failed', 0))}",
                    f"Processed: {processed} / {total_users}",
                ],
                "succeeded": counters.get("succeeded", 0),
                "failed": counters.get("failed", 0),
                "real_errors": counters.get("real_errors", counters.get("failed", 0)),
                "dead_urls": counters.get("dead_urls", 0),
                "skipped": counters.get("skipped", 0),
                "new_avatars": counters.get("new_avatars", 0),
                "unchanged": counters.get("unchanged", 0),
                "processed": processed,
            }
            fetch_step.details = new_details

            if total_users > 0:
                fetch_step.progress_percentage = round(min(processed / total_users * 100, 100), 1)

            # Publish progress update via SSE
            _publish_redis(f"progress:{job.id}", {
                "step_name": fetch_step.step_name,
                "status": fetch_step.status,
                "progress_percentage": fetch_step.progress_percentage,
                "details": new_details,
                "started_at": fetch_step.started_at.isoformat() if fetch_step.started_at else None,
                "completed_at": fetch_step.completed_at.isoformat() if fetch_step.completed_at else None,
            })

            # Check if batch is complete
            if processed >= total_users and total_users > 0:
                failed = counters.get("real_errors", counters.get("failed", 0))
                succeeded = counters.get("succeeded", 0)

                if failed > 0 and succeeded == 0:
                    job.status = "failed"
                else:
                    job.status = "completed"

                job.completed_at = datetime.utcnow()
                fetch_step.status = "completed"
                fetch_step.completed_at = datetime.utcnow()
                fetch_step.progress_percentage = 100.0

                _log_to_job(db, job.id,
                    f"Refresh complete: {succeeded} succeeded ({counters.get('new_avatars', 0)} new, "
                    f"{counters.get('unchanged', 0)} unchanged), {counters.get('dead_urls', 0)} dead URLs skipped, "
                    f"{failed} real errors",
                    step_name="fetch_avatars")

                # Publish job completion via SSE
                _publish_redis(f"progress:{job.id}", {
                    "step_name": "_job",
                    "status": job.status,
                })

                # Trigger OpenSearch update for users who got new avatars
                if counters.get("new_avatars", 0) > 0:
                    sync_avatars_to_opensearch_task.apply_async(queue="io_bound")

            # Auto-timeout stale jobs (running for >2 hours)
            elif job.started_at:
                elapsed = (datetime.utcnow() - job.started_at.replace(tzinfo=None)).total_seconds()
                if elapsed > 7200:
                    job.status = "failed"
                    job.error_message = "Timed out after 2 hours"
                    job.completed_at = datetime.utcnow()
                    fetch_step.status = "failed"
                    fetch_step.completed_at = datetime.utcnow()

        db.commit()
        return {"status": "updated", "jobs_checked": len(running_jobs)}

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating avatar batch stats: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="signal_avatar.auto_refresh_avatars")
def auto_refresh_avatars_task():
    """
    Periodic task (hourly via Celery Beat).
    Checks if auto-refresh is enabled and triggers bulk refresh if interval has elapsed.
    """
    if not is_avatar_auto_refresh_enabled():
        return {"status": "disabled", "message": "Avatar auto-refresh is turned off"}

    interval_hours = get_avatar_refresh_interval_hours()

    db = SessionLocal()
    try:
        # Check last signal_avatar refresh job
        ing_type = db.query(IngestionType).filter(IngestionType.name == "signal_avatar").first()
        if not ing_type:
            return {"status": "no_type"}

        latest_job = (
            db.query(IngestionJob)
            .filter(IngestionJob.ingestion_type_id == ing_type.id)
            .join(IngestionStep, IngestionStep.job_id == IngestionJob.id)
            .filter(IngestionStep.step_name == "fetch_avatars")  # Only refresh jobs
            .order_by(IngestionJob.created_at.desc())
            .first()
        )

        if latest_job and latest_job.started_at:
            elapsed = (datetime.utcnow() - latest_job.started_at.replace(tzinfo=None)).total_seconds()
            if elapsed < interval_hours * 3600:
                return {
                    "status": "skipped",
                    "message": f"Last auto-refresh was {elapsed / 3600:.1f}h ago (interval: {interval_hours}h)",
                }

        # Create IngestionJob for auto-refresh
        job = IngestionJob(status="pending", ingestion_type_id=ing_type.id)
        db.add(job)
        db.flush()

        REFRESH_STEPS = [
            {"step_name": "find_eligible", "step_order": 1, "details": {"description": "Find eligible users"}},
            {"step_name": "fetch_avatars", "step_order": 2, "details": {"description": "Fetch & decrypt avatars from CDN"}},
        ]
        for step_def in REFRESH_STEPS:
            db.add(IngestionStep(
                job_id=job.id, step_name=step_def["step_name"],
                step_order=step_def["step_order"], status="pending",
                progress_percentage=0.0, details=step_def["details"],
            ))
        db.add(IngestionLog(job_id=job.id, message="Auto-refresh triggered", log_level="INFO"))
        db.commit()

        task = orchestrate_bulk_refresh_task.apply_async(
            args=[job.id],
            kwargs={"max_age_hours": interval_hours},
            queue="io_bound",
        )

        job.celery_task_id = task.id
        db.commit()

        logger.info(f"Auto-refresh triggered: job_id={job.id}, interval={interval_hours}h")
        return {"status": "triggered", "job_id": job.id}

    except Exception as e:
        logger.error(f"Error in auto-refresh check: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Import Metadata Task (background SQL parsing)
# ---------------------------------------------------------------------------

def _parse_sql_row(row_str: str) -> list:
    """Parse a single SQL VALUES row into fields."""
    fields = []
    current_field = ""
    in_quotes = False
    i = 0
    while i < len(row_str):
        char = row_str[i]
        if char == '\\':
            current_field += char
            if i + 1 < len(row_str):
                current_field += row_str[i + 1]
                i += 2
            else:
                i += 1
            continue
        if char == "'":
            if not in_quotes:
                in_quotes = True
                current_field += char
            elif i + 1 < len(row_str) and row_str[i + 1] == "'":
                current_field += "''"
                i += 2
                continue
            else:
                in_quotes = False
                current_field += char
            i += 1
            continue
        if not in_quotes and char == ',':
            val = current_field.strip()
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1].replace("''", "'")
            if val.upper() == 'NULL':
                fields.append(None)
            else:
                fields.append(val)
            current_field = ""
            i += 1
            continue
        current_field += char
        i += 1
    if current_field.strip():
        val = current_field.strip()
        if val.startswith("'") and val.endswith("'"):
            val = val[1:-1].replace("''", "'")
        if val.upper() == 'NULL':
            fields.append(None)
        else:
            fields.append(val)
    return fields


@celery_app.task(
    name="signal_avatar.import_metadata",
    bind=True,
    acks_late=True,
)
def import_metadata_task(self, job_id: int, sql_file_path: str):
    """
    Background task: parse user_metadata SQL, store in signal_user_metadata table,
    and update users with remote_avatar_url + profile_key.
    Tracks progress via IngestionJob/Step/Log records.
    """
    import re

    db = SessionLocal()
    try:
        # Mark job as running
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.celery_task_id = self.request.id
            db.commit()

        # --- Step 1: Parse SQL ---
        _update_step(db, job_id, "parse_sql", "running")
        _log_to_job(db, job_id, "Reading SQL file...", step_name="parse_sql")

        with open(sql_file_path, "r", encoding="utf-8", errors="replace") as f:
            sql_content = f.read()

        _log_to_job(db, job_id, f"SQL file loaded ({len(sql_content)} bytes)", step_name="parse_sql")

        # Extract VALUES rows from INSERT statements
        all_metadata = []

        # Find all VALUES positions in one pass (avoids O(n²) re.search per INSERT)
        values_positions = [m.end() for m in re.finditer(r'\)\s*VALUES\s*\n', sql_content, re.IGNORECASE)]
        # Find all INSERT positions to delimit each VALUES section
        insert_positions = [m.start() for m in re.finditer(r'INSERT INTO user_metadata\s*\(', sql_content, re.IGNORECASE)]

        total_inserts = len(values_positions)
        _log_to_job(db, job_id, f"Found {total_inserts} INSERT statements", step_name="parse_sql")

        for idx, values_start in enumerate(values_positions):
            # Determine end of this VALUES section
            # Find the next INSERT that starts AFTER this values_start
            values_end = len(sql_content)
            for ip in insert_positions:
                if ip > values_start:
                    values_end = ip
                    break

            values_section = sql_content[values_start:values_end].rstrip().rstrip(';')

            # Fast row splitting — find top-level (...) groups
            rows = []
            current_row = ""
            paren_depth = 0
            in_q = False
            ci = 0
            vs_len = len(values_section)
            while ci < vs_len:
                ch = values_section[ci]
                if ch == "'" and (ci == 0 or values_section[ci - 1] != '\\'):
                    in_q = not in_q
                    current_row += ch
                    ci += 1
                    continue
                if not in_q:
                    if ch == '(':
                        paren_depth += 1
                        if paren_depth == 1:
                            current_row = ""
                            ci += 1
                            continue
                    elif ch == ')':
                        paren_depth -= 1
                        if paren_depth == 0:
                            rows.append(current_row)
                            current_row = ""
                            ci += 1
                            while ci < vs_len and values_section[ci] in (',', ';', ' ', '\n', '\t'):
                                ci += 1
                            continue
                current_row += ch
                ci += 1

            # Update progress per INSERT statement block
            if total_inserts > 0 and (idx % 100 == 0 or idx == total_inserts - 1):
                pct = round(((idx + 1) / total_inserts) * 90, 1)
                _update_step(db, job_id, "parse_sql", "running", progress=pct)
                if idx % 200 == 0 or idx == total_inserts - 1:
                    _log_to_job(db, job_id, f"Parsing INSERT {idx + 1}/{total_inserts} ({len(all_metadata)} rows so far)", step_name="parse_sql")

            # Field indices from Signal Desktop user_metadata table:
            # 0: serviceId, 1: e164, 2: name, 3: profileName, 4: profileFamilyName,
            # 5: profileFullName, 6: active_at, 7: profileLastFetchedAt, 8: about,
            # 9: aboutEmoji, 10: remoteAvatarUrl, 11: profileKey, 12: profileKeyVersion,
            # 13: accessKey
            for row_str in rows:
                if not row_str.strip():
                    continue
                try:
                    fields = _parse_sql_row(row_str)
                except Exception:
                    continue
                if len(fields) < 12:
                    continue

                service_id = fields[0] if fields[0] else None
                if not service_id:
                    continue

                parsed_row = {
                    "signal_uuid": service_id,
                    "e164": fields[1] if len(fields) > 1 and fields[1] else None,
                    "profile_name": fields[3] if len(fields) > 3 and fields[3] else None,
                    "profile_family_name": fields[4] if len(fields) > 4 and fields[4] else None,
                    "profile_full_name": fields[5] if len(fields) > 5 and fields[5] else None,
                    "remote_avatar_url": fields[10] if len(fields) > 10 and fields[10] else None,
                    "profile_key": fields[11] if len(fields) > 11 and fields[11] else None,
                    "access_key": fields[13] if len(fields) > 13 and fields[13] else None,
                }
                all_metadata.append(parsed_row)

        _log_to_job(db, job_id, f"Parsed {len(all_metadata)} metadata rows from SQL", step_name="parse_sql")
        _update_step(db, job_id, "parse_sql", "completed", progress=100.0, details={
            "total_rows": len(all_metadata),
            "insert_statements": total_inserts,
        })

        if not all_metadata:
            _log_to_job(db, job_id, "No user_metadata rows found in SQL file", level="WARNING", step_name="parse_sql")
            _update_step(db, job_id, "store_metadata", "completed", progress=100.0)
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                db.commit()
            return {"status": "no_data", "total_rows_parsed": 0, "metadata_stored": 0}

        # --- Step 2: Store metadata (bulk upsert, no user_id join needed) ---
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        _update_step(db, job_id, "store_metadata", "running")
        _log_to_job(db, job_id, f"Bulk upserting {len(all_metadata)} rows into signal_user_metadata...", step_name="store_metadata")

        metadata_stored = 0
        batch_sz = 5000  # Large batches for speed

        for i in range(0, len(all_metadata), batch_sz):
            batch = all_metadata[i:i + batch_sz]

            values = [{
                "signal_uuid": row["signal_uuid"],
                "e164": row["e164"],
                "profile_name": row["profile_name"],
                "profile_family_name": row["profile_family_name"],
                "profile_full_name": row["profile_full_name"],
                "remote_avatar_url": row["remote_avatar_url"],
                "profile_key": row["profile_key"],
                "access_key": row["access_key"],
            } for row in batch]

            stmt = pg_insert(SignalUserMetadata).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["signal_uuid"],
                set_={
                    "e164": stmt.excluded.e164,
                    "profile_name": stmt.excluded.profile_name,
                    "profile_family_name": stmt.excluded.profile_family_name,
                    "profile_full_name": stmt.excluded.profile_full_name,
                    "remote_avatar_url": stmt.excluded.remote_avatar_url,
                    "profile_key": stmt.excluded.profile_key,
                    "access_key": stmt.excluded.access_key,
                },
            )
            db.execute(stmt)
            db.commit()

            metadata_stored += len(batch)
            pct = min(100.0, round(((i + len(batch)) / len(all_metadata)) * 100, 1))
            _update_step(db, job_id, "store_metadata", "running", progress=pct)

        _log_to_job(db, job_id, f"Stored {metadata_stored} metadata rows", step_name="store_metadata")
        _update_step(db, job_id, "store_metadata", "completed", progress=100.0, details={
            "metadata_stored": metadata_stored,
        })

        # --- Step 3: Cleanup ---
        _update_step(db, job_id, "cleanup", "running")
        _log_to_job(db, job_id, f"Removing uploaded file: {os.path.basename(sql_file_path)}", step_name="cleanup")
        try:
            os.unlink(sql_file_path)
            _log_to_job(db, job_id, "Uploaded file removed", step_name="cleanup")
        except Exception as e:
            _log_to_job(db, job_id, f"Could not remove file: {e}", level="WARNING", step_name="cleanup")
        _update_step(db, job_id, "cleanup", "completed", progress=100.0)

        # Mark job completed
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            db.commit()

        _log_to_job(db, job_id, f"Import complete: {len(all_metadata)} parsed, {metadata_stored} stored")
        _publish_redis(f"progress:{job_id}", {"step_name": "_job", "status": "completed"})

        return {
            "status": "success",
            "total_rows_parsed": len(all_metadata),
            "metadata_stored": metadata_stored,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error importing avatar metadata: {e}", exc_info=True)
        # Mark job failed
        try:
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
            _log_to_job(db, job_id, f"Import failed: {e}", level="ERROR")
        except Exception:
            pass
        raise

    finally:
        db.close()


@celery_app.task(name="signal_avatar.sync_avatars_to_opensearch")
def sync_avatars_to_opensearch_task():
    """
    Bulk update sender_avatar_file_id in OpenSearch signal_messages index
    for all users who have avatars in signal_user_metadata.
    """
    from app.db.session import os_client as opensearch_client

    db = SessionLocal()
    try:
        # Get all users with avatars
        rows = (
            db.query(User.signal_uuid, SignalUserMetadata.avatar_file_id)
            .join(SignalUserMetadata, User.signal_uuid == SignalUserMetadata.signal_uuid)
            .filter(SignalUserMetadata.avatar_file_id.isnot(None))
            .all()
        )

        if not rows:
            logger.info("No users with avatars to sync to OpenSearch")
            return {"status": "no_data"}

        uuid_to_avatar = {uuid: file_id for uuid, file_id in rows}
        logger.info(f"Syncing {len(uuid_to_avatar)} user avatars to OpenSearch")

        bulk_body = []
        batch_size = 2000
        updated = 0

        for signal_uuid, avatar_file_id in uuid_to_avatar.items():
            try:
                result = opensearch_client.search(
                    index="signal_messages",
                    body={
                        "query": {"term": {"sender_signal_uuid": signal_uuid}},
                        "_source": False,
                        "size": 10000,
                    },
                )
                for hit in result.get("hits", {}).get("hits", []):
                    bulk_body.append({"update": {"_index": "signal_messages", "_id": hit["_id"]}})
                    bulk_body.append({"doc": {"sender_avatar_file_id": avatar_file_id}})

                if len(bulk_body) >= batch_size * 2:
                    opensearch_client.bulk(body=bulk_body, refresh=False)
                    updated += len(bulk_body) // 2
                    bulk_body = []
            except Exception as e:
                logger.warning(f"Error updating OpenSearch for {signal_uuid[:12]}: {e}")
                continue

        if bulk_body:
            opensearch_client.bulk(body=bulk_body, refresh=True)
            updated += len(bulk_body) // 2

        logger.info(f"Synced {updated} OpenSearch documents with avatar_file_id")
        return {"status": "success", "documents_updated": updated}

    except Exception as e:
        logger.error(f"Error syncing avatars to OpenSearch: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
