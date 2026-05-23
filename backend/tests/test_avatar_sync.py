"""
Test Suite for Avatar Sync Part B: Continuous Scheduled Revalidation

Tests:
1. _verify_single_avatar — all paths (unchanged, changed, missing, error, etag_variance)
2. trigger_scheduled_avatar_sync — kill switch, S3 check, interval throttle, collision detection
3. S3 helpers — head_s3_object, get_s3_object_body
4. Config — default values
5. Schema — new Avatar columns, AvatarSyncAuditLog model
6. Smart filtering — change_frequency, update logic
7. Timeout & alerting — check_timeout_exceeded, check_alert_threshold
8. Audit utils — log_avatar_sync_audit, batch logging
9. FIFO enforcement — _check_and_queue_if_blocked

Run with conda env:
  D:\\Users\\bhavi\\miniconda3\\envs\\user-search\\python.exe test_avatar_sync.py
"""

import sys
import os
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

# Add the backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pre-import all models to resolve SQLAlchemy mapper relationships
# (IngestionJob has a relationship to AppUser - both must be loaded)
import app.db.schemas.app_models  # noqa: F401
import app.db.schemas.ingestion_models  # noqa: F401
import app.db.schemas.api_key_models  # noqa: F401
import app.db.schemas.stripe_models  # noqa: F401

# Track test results
passed = 0
failed = 0
errors = []


def run_test(name, func):
    """Run a test function and track results."""
    global passed, failed, errors
    try:
        func()
        passed += 1
        print(f"  PASS: {name}")
    except AssertionError as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  FAIL: {name} — {e}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ERROR: {name} — {e}")


# ---------------------------------------------------------------------------
# Mock Helpers
# ---------------------------------------------------------------------------

class MockAvatar:
    """Mock Avatar model for testing."""

    def __init__(
        self,
        id=1,
        service_id="test-service-123",
        s3_key="avatars/test-service-123/profile.jpg",
        s3_url="https://s3.example.com/avatars/test-service-123/profile.jpg",
        filename="profile.jpg",
        file_size=1024,
        snapshot_hash=None,
        stored_etag=None,
        last_verified_at=None,
        verification_status=None,
        change_frequency=None,
        failure_reason=None,
    ):
        self.id = id
        self.service_id = service_id
        self.s3_key = s3_key
        self.s3_url = s3_url
        self.filename = filename
        self.file_size = file_size
        self.snapshot_hash = snapshot_hash or hashlib.sha256(b"original_content").digest()
        self.stored_etag = stored_etag
        self.last_verified_at = last_verified_at
        self.verification_status = verification_status
        self.change_frequency = change_frequency
        self.failure_reason = failure_reason


class MockJob:
    """Mock IngestionJob model."""

    def __init__(self, id=1, status="pending", ingestion_type="avatar_sync"):
        self.id = id
        self.status = status
        self.ingestion_type = ingestion_type
        self.created_at = datetime.now(timezone.utc)
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.metrics = {}
        self.celery_task_id = None


# ===========================================================================
# _verify_single_avatar Tests
# ===========================================================================

def test_verify_unchanged_avatar():
    """Avatar unchanged: HEAD returns same size + ETag -> no download, just update last_verified_at."""
    from app.tasks.avatar_sync_tasks import _verify_single_avatar

    avatar = MockAvatar(
        file_size=1024,
        stored_etag="abc123etag",
        snapshot_hash=hashlib.sha256(b"content").digest(),
        change_frequency="MEDIUM",
    )
    stats = {"checked": 0, "unchanged": 0, "changed": 0, "missing": 0, "errors": 0}
    mock_db = MagicMock()

    with patch("app.tasks.avatar_sync_tasks.head_s3_object") as mock_head:
        mock_head.return_value = {
            "ContentLength": 1024,
            "ETag": '"abc123etag"',
        }
        _verify_single_avatar(mock_db, avatar, job_id=1, stats=stats)

    assert stats["checked"] == 1
    assert stats["unchanged"] == 1
    assert avatar.last_verified_at is not None
    assert avatar.verification_status == "verified"
    assert avatar.failure_reason is None
    # MEDIUM unchanged -> demotes to LOW
    assert avatar.change_frequency == "LOW"


def test_verify_missing_avatar():
    """Avatar missing: HEAD returns None (404) -> log audit 'missing'."""
    from app.tasks.avatar_sync_tasks import _verify_single_avatar

    avatar = MockAvatar(change_frequency="HIGH")
    stats = {"checked": 0, "unchanged": 0, "changed": 0, "missing": 0, "errors": 0}
    mock_db = MagicMock()

    with patch("app.tasks.avatar_sync_tasks.head_s3_object") as mock_head:
        mock_head.return_value = None
        _verify_single_avatar(mock_db, avatar, job_id=1, stats=stats)

    assert stats["missing"] == 1
    assert avatar.verification_status == "missing"
    assert avatar.failure_reason == "S3_OBJECT_NOT_FOUND"
    # HIGH unchanged -> demotes to MEDIUM
    assert avatar.change_frequency == "MEDIUM"


def test_verify_changed_avatar():
    """Avatar changed: HEAD shows different ETag, download confirms different hash."""
    from app.tasks.avatar_sync_tasks import _verify_single_avatar

    original_hash = hashlib.sha256(b"original_content").digest()
    new_content = b"new_content_here"
    new_hash = hashlib.sha256(new_content).digest()

    avatar = MockAvatar(
        file_size=1024,
        stored_etag="old_etag",
        snapshot_hash=original_hash,
        change_frequency="LOW",
    )
    stats = {"checked": 0, "unchanged": 0, "changed": 0, "missing": 0, "errors": 0}
    mock_db = MagicMock()

    with (
        patch("app.tasks.avatar_sync_tasks.head_s3_object") as mock_head,
        patch("app.tasks.avatar_sync_tasks.get_s3_object_body") as mock_download,
    ):
        mock_head.return_value = {"ContentLength": len(new_content), "ETag": '"new_etag_456"'}
        mock_download.return_value = new_content
        _verify_single_avatar(mock_db, avatar, job_id=1, stats=stats)

    assert stats["changed"] == 1
    assert avatar.snapshot_hash == new_hash
    assert avatar.file_size == len(new_content)
    assert avatar.stored_etag == "new_etag_456"
    assert avatar.verification_status == "changed"
    assert avatar.failure_reason is None
    # LOW changed -> promotes to MEDIUM
    assert avatar.change_frequency == "MEDIUM"
    # Audit log created
    mock_db.add.assert_called_once()
    assert mock_db.add.call_args[0][0].action == "changed"


def test_verify_etag_variance():
    """ETag changed but content hash identical -> update ETag only, log etag_updated."""
    from app.tasks.avatar_sync_tasks import _verify_single_avatar

    content = b"same_content"
    content_hash = hashlib.sha256(content).digest()

    avatar = MockAvatar(file_size=500, stored_etag="old_etag", snapshot_hash=content_hash)
    stats = {"checked": 0, "unchanged": 0, "changed": 0, "missing": 0, "errors": 0}
    mock_db = MagicMock()

    with (
        patch("app.tasks.avatar_sync_tasks.head_s3_object") as mock_head,
        patch("app.tasks.avatar_sync_tasks.get_s3_object_body") as mock_download,
    ):
        mock_head.return_value = {"ContentLength": len(content), "ETag": '"new_etag_789"'}
        mock_download.return_value = content
        _verify_single_avatar(mock_db, avatar, job_id=1, stats=stats)

    assert stats["unchanged"] == 1
    assert avatar.stored_etag == "new_etag_789"
    assert avatar.verification_status == "etag_variance"
    mock_db.add.assert_called_once()
    assert mock_db.add.call_args[0][0].action == "etag_updated"


def test_verify_download_failure():
    """S3 download returns None -> log error."""
    from app.tasks.avatar_sync_tasks import _verify_single_avatar

    avatar = MockAvatar(file_size=500, stored_etag="old_etag")
    stats = {"checked": 0, "unchanged": 0, "changed": 0, "missing": 0, "errors": 0}
    mock_db = MagicMock()

    with (
        patch("app.tasks.avatar_sync_tasks.head_s3_object") as mock_head,
        patch("app.tasks.avatar_sync_tasks.get_s3_object_body") as mock_download,
    ):
        mock_head.return_value = {"ContentLength": 999, "ETag": '"different_etag"'}
        mock_download.return_value = None
        _verify_single_avatar(mock_db, avatar, job_id=1, stats=stats)

    assert stats["errors"] == 1
    assert avatar.verification_status == "failed"
    assert avatar.failure_reason == "DOWNLOAD_FAILED"


def test_verify_first_time():
    """First verification: no stored_etag -> must download. Content matches -> unchanged."""
    from app.tasks.avatar_sync_tasks import _verify_single_avatar

    content = b"test_content"
    content_hash = hashlib.sha256(content).digest()
    avatar = MockAvatar(file_size=len(content), stored_etag=None, snapshot_hash=content_hash)
    stats = {"checked": 0, "unchanged": 0, "changed": 0, "missing": 0, "errors": 0}
    mock_db = MagicMock()

    with (
        patch("app.tasks.avatar_sync_tasks.head_s3_object") as mock_head,
        patch("app.tasks.avatar_sync_tasks.get_s3_object_body") as mock_download,
    ):
        mock_head.return_value = {"ContentLength": len(content), "ETag": '"first_etag"'}
        mock_download.return_value = content
        _verify_single_avatar(mock_db, avatar, job_id=1, stats=stats)

    assert stats["unchanged"] == 1
    assert avatar.stored_etag == "first_etag"
    assert avatar.verification_status == "etag_variance"


def test_verify_head_error_propagates():
    """When HEAD request raises a non-404 error, it should propagate."""
    from app.tasks.avatar_sync_tasks import _verify_single_avatar

    avatar = MockAvatar()
    stats = {"checked": 0, "unchanged": 0, "changed": 0, "missing": 0, "errors": 0}
    mock_db = MagicMock()

    with patch("app.tasks.avatar_sync_tasks.head_s3_object") as mock_head:
        mock_head.side_effect = Exception("S3 connection error")
        raised = False
        try:
            _verify_single_avatar(mock_db, avatar, job_id=1, stats=stats)
        except Exception as e:
            raised = True
            assert "S3 connection error" in str(e)
        assert raised


# ===========================================================================
# change_frequency Tests
# ===========================================================================

def test_change_frequency_promote_low_to_medium():
    """LOW avatar that changed should promote to MEDIUM."""
    from app.utils.avatar_sync_utils import update_change_frequency
    avatar = MockAvatar(change_frequency="LOW")
    update_change_frequency(avatar, changed=True)
    assert avatar.change_frequency == "MEDIUM"


def test_change_frequency_promote_medium_to_high():
    """MEDIUM avatar that changed should promote to HIGH."""
    from app.utils.avatar_sync_utils import update_change_frequency
    avatar = MockAvatar(change_frequency="MEDIUM")
    update_change_frequency(avatar, changed=True)
    assert avatar.change_frequency == "HIGH"


def test_change_frequency_high_stays_high():
    """HIGH avatar that changed stays HIGH."""
    from app.utils.avatar_sync_utils import update_change_frequency
    avatar = MockAvatar(change_frequency="HIGH")
    update_change_frequency(avatar, changed=True)
    assert avatar.change_frequency == "HIGH"


def test_change_frequency_demote_high_to_medium():
    """HIGH avatar unchanged should demote to MEDIUM."""
    from app.utils.avatar_sync_utils import update_change_frequency
    avatar = MockAvatar(change_frequency="HIGH")
    update_change_frequency(avatar, changed=False)
    assert avatar.change_frequency == "MEDIUM"


def test_change_frequency_demote_medium_to_low():
    """MEDIUM avatar unchanged should demote to LOW."""
    from app.utils.avatar_sync_utils import update_change_frequency
    avatar = MockAvatar(change_frequency="MEDIUM")
    update_change_frequency(avatar, changed=False)
    assert avatar.change_frequency == "LOW"


def test_change_frequency_low_stays_low():
    """LOW avatar unchanged stays LOW."""
    from app.utils.avatar_sync_utils import update_change_frequency
    avatar = MockAvatar(change_frequency="LOW")
    update_change_frequency(avatar, changed=False)
    assert avatar.change_frequency == "LOW"


def test_change_frequency_none_changed():
    """NULL frequency avatar that changed should become MEDIUM."""
    from app.utils.avatar_sync_utils import update_change_frequency
    avatar = MockAvatar(change_frequency=None)
    update_change_frequency(avatar, changed=True)
    assert avatar.change_frequency == "MEDIUM"


def test_change_frequency_none_unchanged():
    """NULL frequency avatar unchanged should become LOW."""
    from app.utils.avatar_sync_utils import update_change_frequency
    avatar = MockAvatar(change_frequency=None)
    update_change_frequency(avatar, changed=False)
    assert avatar.change_frequency == "LOW"


# ===========================================================================
# Timeout & Alert Tests
# ===========================================================================

def test_timeout_not_exceeded():
    """Job within timeout should return False."""
    from app.utils.avatar_sync_utils import check_timeout_exceeded
    started = datetime.now(timezone.utc) - timedelta(minutes=10)
    exceeded, elapsed = check_timeout_exceeded(started)
    assert not exceeded
    assert 590 < elapsed < 620  # ~600 seconds


def test_timeout_exceeded():
    """Job past timeout should return True."""
    from app.utils.avatar_sync_utils import check_timeout_exceeded
    started = datetime.now(timezone.utc) - timedelta(hours=2)
    exceeded, elapsed = check_timeout_exceeded(started)
    assert exceeded
    assert elapsed > 7000


def test_timeout_none_start():
    """None start time should not trigger timeout."""
    from app.utils.avatar_sync_utils import check_timeout_exceeded
    exceeded, elapsed = check_timeout_exceeded(None)
    assert not exceeded
    assert elapsed == 0.0


def test_alert_not_triggered():
    """Job within alert threshold should return False."""
    from app.utils.avatar_sync_utils import check_alert_threshold
    started = datetime.now(timezone.utc) - timedelta(minutes=5)
    should_alert, elapsed = check_alert_threshold(started)
    assert not should_alert


def test_alert_triggered():
    """Job past alert threshold should return True."""
    from app.utils.avatar_sync_utils import check_alert_threshold
    started = datetime.now(timezone.utc) - timedelta(minutes=45)
    should_alert, elapsed = check_alert_threshold(started)
    assert should_alert
    assert elapsed > 2600


# ===========================================================================
# Audit Utility Tests
# ===========================================================================

def test_log_avatar_sync_audit():
    """log_avatar_sync_audit should create an AvatarSyncAuditLog entry."""
    from app.utils.avatar_sync_audit import log_avatar_sync_audit

    mock_db = MagicMock()
    avatar = MockAvatar()
    old_hash = b"\x01" * 32
    new_hash = b"\x02" * 32

    log_avatar_sync_audit(
        mock_db, avatar, action="changed", detail="Hash changed",
        job_id=5, old_hash=old_hash, new_hash=new_hash,
        old_file_size=1024, new_file_size=2048,
    )

    mock_db.add.assert_called_once()
    entry = mock_db.add.call_args[0][0]
    assert entry.avatar_id == avatar.id
    assert entry.service_id == avatar.service_id
    assert entry.action == "changed"
    assert entry.old_hash == old_hash
    assert entry.new_hash == new_hash


def test_batch_log_empty():
    """batch_log with empty list should return 0."""
    from app.utils.avatar_sync_audit import batch_log_avatar_sync_audits
    mock_db = MagicMock()
    result = batch_log_avatar_sync_audits(mock_db, [])
    assert result == 0


def test_batch_log_records():
    """batch_log should insert records via bulk_insert_mappings."""
    from app.utils.avatar_sync_audit import batch_log_avatar_sync_audits
    mock_db = MagicMock()
    records = [
        {"avatar_id": 1, "service_id": "svc1", "action": "changed", "job_id": 1},
        {"avatar_id": 2, "service_id": "svc2", "action": "missing", "job_id": 1},
    ]
    result = batch_log_avatar_sync_audits(mock_db, records)
    assert result == 2
    mock_db.bulk_insert_mappings.assert_called_once()


# ===========================================================================
# trigger_scheduled_avatar_sync Tests
# ===========================================================================

def test_trigger_kill_switch_disabled():
    """When AVATAR_SYNC_ENABLED=False, trigger should return immediately."""
    from app.tasks.avatar_sync_tasks import trigger_scheduled_avatar_sync
    with patch("app.tasks.avatar_sync_tasks.settings") as mock_settings:
        mock_settings.AVATAR_SYNC_ENABLED = False
        with patch("app.tasks.avatar_sync_tasks.SessionLocal") as mock_session:
            trigger_scheduled_avatar_sync()
            mock_session.assert_not_called()


def test_trigger_s3_not_configured():
    """When S3 is not configured, trigger should skip."""
    from app.tasks.avatar_sync_tasks import trigger_scheduled_avatar_sync
    with (
        patch("app.tasks.avatar_sync_tasks.settings") as mock_settings,
        patch("app.tasks.avatar_sync_tasks.get_s3_client") as mock_s3,
        patch("app.tasks.avatar_sync_tasks.SessionLocal") as mock_session,
    ):
        mock_settings.AVATAR_SYNC_ENABLED = True
        mock_s3.return_value = None
        trigger_scheduled_avatar_sync()
        mock_session.assert_not_called()


def test_trigger_existing_running_job():
    """When an avatar_sync job is already running, trigger should skip."""
    from app.tasks.avatar_sync_tasks import trigger_scheduled_avatar_sync
    mock_db = MagicMock()
    mock_existing_job = MockJob(id=5, status="running")
    with (
        patch("app.tasks.avatar_sync_tasks.settings") as mock_settings,
        patch("app.tasks.avatar_sync_tasks.get_s3_client") as mock_s3,
        patch("app.tasks.avatar_sync_tasks.SessionLocal", return_value=mock_db),
        patch("app.tasks.avatar_sync_tasks.run_avatar_sync_batch") as mock_batch,
    ):
        mock_settings.AVATAR_SYNC_ENABLED = True
        mock_settings.AVATAR_SYNC_INTERVAL_HOURS = 24
        mock_s3.return_value = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing_job
        trigger_scheduled_avatar_sync()
        mock_batch.apply_async.assert_not_called()


def test_trigger_success():
    """When all checks pass, trigger should create job and dispatch batch."""
    from app.tasks.avatar_sync_tasks import trigger_scheduled_avatar_sync
    mock_db = MagicMock()
    new_job = MockJob(id=10, status="pending")
    with (
        patch("app.tasks.avatar_sync_tasks.settings") as mock_settings,
        patch("app.tasks.avatar_sync_tasks.get_s3_client") as mock_s3,
        patch("app.tasks.avatar_sync_tasks.SessionLocal", return_value=mock_db),
        patch("app.tasks.avatar_sync_tasks.run_avatar_sync_batch") as mock_batch,
        patch("app.tasks.avatar_sync_tasks.JobsController") as mock_jc,
    ):
        mock_settings.AVATAR_SYNC_ENABLED = True
        mock_settings.AVATAR_SYNC_INTERVAL_HOURS = 24
        mock_s3.return_value = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_jc.create_job.return_value = new_job
        trigger_scheduled_avatar_sync()
        mock_jc.create_job.assert_called_once_with(db=mock_db, ingestion_type="avatar_sync", celery_task_id=None)
        mock_batch.apply_async.assert_called_once_with(args=[10, 0], queue="avatars")


# ===========================================================================
# Helper Tests
# ===========================================================================

def test_fail_job():
    """_fail_job should mark job as failed."""
    from app.tasks.avatar_sync_tasks import _fail_job
    mock_db = MagicMock()
    mock_job = MockJob(id=1, status="running")
    with patch("app.tasks.avatar_sync_tasks.JobsController") as mock_jc:
        mock_jc.get_job.return_value = mock_job
        _fail_job(mock_db, 1, "Test error")
    assert mock_job.status == "failed"
    assert mock_job.error_message == "Test error"
    mock_db.commit.assert_called_once()


def test_storage_limit_ok():
    """When storage is below threshold, should not raise."""
    from app.tasks.avatar_sync_tasks import _enforce_storage_limit
    mock_db = MagicMock()
    mock_log = MagicMock()
    with patch("app.tasks.avatar_sync_tasks.is_storage_critical", return_value=False):
        _enforce_storage_limit(mock_db, job_id=1, db_log=mock_log)
    mock_log.assert_not_called()


def test_storage_limit_critical():
    """When storage > 90%, should fail job and raise."""
    from app.tasks.avatar_sync_tasks import _enforce_storage_limit
    mock_db = MagicMock()
    mock_log = MagicMock()
    with (
        patch("app.tasks.avatar_sync_tasks.is_storage_critical", return_value=True),
        patch("app.tasks.avatar_sync_tasks.get_disk_usage_percent", return_value=0.95),
        patch("app.tasks.avatar_sync_tasks.JobsController") as mock_jc,
    ):
        mock_jc.get_job.return_value = MockJob(id=1)
        raised = False
        try:
            _enforce_storage_limit(mock_db, job_id=1, db_log=mock_log)
        except Exception as e:
            raised = True
            assert "95.0%" in str(e)
        assert raised


def test_fifo_no_blocking():
    """When no older active jobs exist, should mark job running."""
    from app.tasks.avatar_sync_tasks import _check_and_queue_if_blocked
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("app.tasks.avatar_sync_tasks.JobsController") as mock_jc:
        _check_and_queue_if_blocked(mock_db, job_id=5, db_log=MagicMock(), retry_exc=MagicMock())
        mock_jc.mark_job_running.assert_called_once_with(mock_db, 5)


def test_fifo_blocked():
    """When an older active job exists, should raise retry."""
    from app.tasks.avatar_sync_tasks import _check_and_queue_if_blocked
    mock_db = MagicMock()
    class RetryException(Exception): pass
    def mock_retry(countdown=10): raise RetryException()
    older_job = MockJob(id=3, status="running")
    mock_db.query.return_value.filter.return_value.first.return_value = older_job
    current_job = MockJob(id=5, status="pending")
    with patch("app.tasks.avatar_sync_tasks.JobsController") as mock_jc:
        mock_jc.get_job.return_value = current_job
        raised = False
        try:
            _check_and_queue_if_blocked(mock_db, job_id=5, db_log=MagicMock(), retry_exc=mock_retry)
        except RetryException:
            raised = True
        assert raised
        assert current_job.status == "queued"


# ===========================================================================
# S3 Helper Tests
# ===========================================================================

def test_head_s3_object_not_configured():
    from app.core.s3 import head_s3_object
    with patch("app.core.s3.get_s3_client", return_value=None):
        assert head_s3_object("test/key.jpg") is None


def test_head_s3_object_404():
    from app.core.s3 import head_s3_object
    mock_client = MagicMock()
    mock_error = Exception("Not Found")
    mock_error.response = {"Error": {"Code": "404"}}
    mock_client.head_object.side_effect = mock_error
    with patch("app.core.s3.get_s3_client", return_value=mock_client):
        assert head_s3_object("test/key.jpg") is None


def test_head_s3_object_success():
    from app.core.s3 import head_s3_object
    mock_client = MagicMock()
    mock_client.head_object.return_value = {"ContentLength": 2048, "ETag": '"abc123"'}
    with patch("app.core.s3.get_s3_client", return_value=mock_client):
        result = head_s3_object("test/key.jpg")
        assert result["ContentLength"] == 2048


def test_get_s3_object_body_success():
    from app.core.s3 import get_s3_object_body
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"file_content_here"
    mock_client.get_object.return_value = {"Body": mock_body}
    with patch("app.core.s3.get_s3_client", return_value=mock_client):
        assert get_s3_object_body("test/key.jpg") == b"file_content_here"


def test_get_s3_object_body_not_configured():
    from app.core.s3 import get_s3_object_body
    with patch("app.core.s3.get_s3_client", return_value=None):
        assert get_s3_object_body("test/key.jpg") is None


# ===========================================================================
# Config & Schema Tests
# ===========================================================================

def test_config_defaults():
    """Verify avatar sync config defaults are set correctly."""
    from app.core.config import settings
    assert settings.AVATAR_SYNC_ENABLED is False
    assert settings.AVATAR_SYNC_INTERVAL_HOURS == 24
    assert settings.AVATAR_SYNC_BATCH_SIZE == 100
    assert settings.AVATAR_SYNC_BATCH_DELAY_SECONDS == 2
    assert settings.AVATAR_SYNC_MAX_RETRIES == 2
    assert settings.AVATAR_SYNC_DOWNLOAD_TIMEOUT == 5
    # Smart filtering
    assert settings.AVATAR_SYNC_CHECK_HIGH_FREQ_HOURS == 6
    assert settings.AVATAR_SYNC_CHECK_MEDIUM_FREQ_HOURS == 72
    assert settings.AVATAR_SYNC_CHECK_LOW_FREQ_HOURS == 168
    assert settings.AVATAR_SYNC_CHECK_NEVER_VERIFIED_HOURS == 24
    # Rate limiting
    assert settings.AVATAR_SYNC_HEAD_REQUESTS_PER_SEC == 100
    assert settings.AVATAR_SYNC_S3_QUOTA_LIMIT_PER_SEC == 1000
    assert settings.AVATAR_SYNC_RETRY_BACKOFF_BASE == 0.5
    # Timeout & alerting
    assert settings.AVATAR_SYNC_TIMEOUT_SECONDS == 3600
    assert settings.AVATAR_SYNC_ALERT_IF_EXCEEDS_SECONDS == 1800


def test_avatar_model_columns():
    """Verify Avatar model has all sync columns."""
    from app.db.schemas.ingestion_models import Avatar
    column_names = [c.key for c in Avatar.__table__.columns]
    for col in ["stored_etag", "last_verified_at", "verification_status", "change_frequency", "failure_reason"]:
        assert col in column_names, f"Avatar should have '{col}' column"


def test_audit_log_model():
    """Verify AvatarSyncAuditLog model has all required columns."""
    from app.db.schemas.ingestion_models import AvatarSyncAuditLog
    column_names = [c.key for c in AvatarSyncAuditLog.__table__.columns]
    expected = ["id", "avatar_id", "service_id", "s3_key", "action", "detail",
                "old_hash", "new_hash", "old_file_size", "new_file_size", "job_id", "created_at"]
    for col in expected:
        assert col in column_names, f"AvatarSyncAuditLog should have '{col}' column"


def test_celery_beat_schedule():
    from app.core.celery_app import celery_app
    schedule = celery_app.conf.beat_schedule
    assert "trigger-scheduled-avatar-sync" in schedule
    assert schedule["trigger-scheduled-avatar-sync"]["task"] == "avatar_sync_tasks.trigger_scheduled_avatar_sync"


def test_celery_task_routing():
    from app.core.celery_app import celery_app
    routes = celery_app.conf.task_routes
    assert routes["avatar_sync_tasks.run_avatar_sync_batch"]["queue"] == "avatars"


def test_celery_imports():
    from app.core.celery_app import celery_app
    assert "app.tasks.avatar_sync_tasks" in celery_app.conf.imports


def test_substep_definitions():
    from app.utils.ingestion_helpers import SUBSTEP_DEFINITIONS
    assert "avatar_sync" in SUBSTEP_DEFINITIONS
    substeps = SUBSTEP_DEFINITIONS["avatar_sync"]
    assert "Filtering Avatars" in substeps
    assert "Verifying Against S3" in substeps


# ===========================================================================
# Retry backoff test
# ===========================================================================

def test_retry_backoff():
    """Backoff should increase exponentially and cap at 30s."""
    from app.utils.avatar_sync_utils import retry_with_backoff
    assert retry_with_backoff(0) == 0.5   # 0.5 * 2^0
    assert retry_with_backoff(1) == 1.0   # 0.5 * 2^1
    assert retry_with_backoff(2) == 2.0   # 0.5 * 2^2
    assert retry_with_backoff(10) == 30.0  # capped at 30


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Avatar Sync Part B — Test Suite")
    print("=" * 70)

    print("\n--- _verify_single_avatar Tests ---")
    run_test("Unchanged avatar (ETag + size match)", test_verify_unchanged_avatar)
    run_test("Missing avatar (404)", test_verify_missing_avatar)
    run_test("Changed avatar (hash differs)", test_verify_changed_avatar)
    run_test("ETag variance (false positive)", test_verify_etag_variance)
    run_test("Download failure", test_verify_download_failure)
    run_test("First-time verification (no stored_etag)", test_verify_first_time)
    run_test("HEAD error propagation (non-404)", test_verify_head_error_propagates)

    print("\n--- change_frequency Tests ---")
    run_test("Promote LOW -> MEDIUM on change", test_change_frequency_promote_low_to_medium)
    run_test("Promote MEDIUM -> HIGH on change", test_change_frequency_promote_medium_to_high)
    run_test("HIGH stays HIGH on change", test_change_frequency_high_stays_high)
    run_test("Demote HIGH -> MEDIUM on unchanged", test_change_frequency_demote_high_to_medium)
    run_test("Demote MEDIUM -> LOW on unchanged", test_change_frequency_demote_medium_to_low)
    run_test("LOW stays LOW on unchanged", test_change_frequency_low_stays_low)
    run_test("NULL -> MEDIUM on change", test_change_frequency_none_changed)
    run_test("NULL -> LOW on unchanged", test_change_frequency_none_unchanged)

    print("\n--- Timeout & Alert Tests ---")
    run_test("Timeout not exceeded", test_timeout_not_exceeded)
    run_test("Timeout exceeded", test_timeout_exceeded)
    run_test("Timeout with None start", test_timeout_none_start)
    run_test("Alert not triggered", test_alert_not_triggered)
    run_test("Alert triggered", test_alert_triggered)

    print("\n--- Audit Utility Tests ---")
    run_test("log_avatar_sync_audit creates entry", test_log_avatar_sync_audit)
    run_test("batch_log empty list", test_batch_log_empty)
    run_test("batch_log records", test_batch_log_records)

    print("\n--- trigger_scheduled_avatar_sync Tests ---")
    run_test("Kill switch disabled", test_trigger_kill_switch_disabled)
    run_test("S3 not configured", test_trigger_s3_not_configured)
    run_test("Existing running job", test_trigger_existing_running_job)
    run_test("Successful dispatch", test_trigger_success)

    print("\n--- Helper Function Tests ---")
    run_test("_fail_job marks job failed", test_fail_job)
    run_test("Storage limit OK", test_storage_limit_ok)
    run_test("Storage limit critical", test_storage_limit_critical)
    run_test("FIFO — no blocking", test_fifo_no_blocking)
    run_test("FIFO — blocked by older job", test_fifo_blocked)

    print("\n--- S3 Helper Tests ---")
    run_test("head_s3_object — not configured", test_head_s3_object_not_configured)
    run_test("head_s3_object — 404", test_head_s3_object_404)
    run_test("head_s3_object — success", test_head_s3_object_success)
    run_test("get_s3_object_body — success", test_get_s3_object_body_success)
    run_test("get_s3_object_body — not configured", test_get_s3_object_body_not_configured)

    print("\n--- Config & Schema Tests ---")
    run_test("Config defaults", test_config_defaults)
    run_test("Avatar model columns (5 sync cols)", test_avatar_model_columns)
    run_test("AvatarSyncAuditLog model", test_audit_log_model)
    run_test("Celery beat schedule", test_celery_beat_schedule)
    run_test("Celery task routing", test_celery_task_routing)
    run_test("Celery imports", test_celery_imports)
    run_test("Substep definitions", test_substep_definitions)

    print("\n--- Retry Backoff Test ---")
    run_test("Retry backoff exponential + cap", test_retry_backoff)

    # --- Summary ---
    print("\n" + "=" * 70)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")

    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")

    print("=" * 70)
    sys.exit(1 if failed > 0 else 0)
