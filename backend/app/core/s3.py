import logging
import os
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)

_s3_client = None


def get_s3_client():
    """Returns a boto3 S3 client, or None if S3 is not configured."""
    global _s3_client
    if not settings.S3_BUCKET_NAME:
        return None
    if _s3_client is not None:
        return _s3_client
    try:
        import boto3
        kwargs = {
            "region_name": settings.S3_REGION,
        }
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        if settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
            kwargs["aws_access_key_id"] = settings.S3_ACCESS_KEY
            kwargs["aws_secret_access_key"] = settings.S3_SECRET_KEY
        _s3_client = boto3.client("s3", **kwargs)
        return _s3_client
    except ImportError:
        logger.warning("boto3 not installed. S3 operations will be skipped.")
        return None
    except Exception as e:
        logger.warning(f"Failed to create S3 client: {e}")
        return None


def head_s3_object(s3_key: str) -> dict | None:
    """
    HEAD request to S3. Returns metadata dict (ContentLength, ETag, etc.),
    or None if object not found (404) or S3 is not configured.
    Raises on other S3 errors.
    """
    client = get_s3_client()
    if client is None:
        logger.info(f"S3 not configured, skipping HEAD for {s3_key}")
        return None
    try:
        return client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    except Exception as e:
        # HEAD requests return 404 as ClientError, not NoSuchKey
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchKey"):
            return None
        logger.warning(f"HEAD request failed for {s3_key}: {e}")
        raise


def get_s3_object_body(s3_key: str) -> bytes | None:
    """
    Downloads and returns the body of an S3 object as bytes.
    Returns None if S3 is not configured.
    """
    client = get_s3_client()
    if client is None:
        logger.info(f"S3 not configured, skipping download for {s3_key}")
        return None
    try:
        response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return response["Body"].read()
    except Exception as e:
        logger.warning(f"Failed to download S3 object {s3_key}: {e}")
        raise


def put_s3_object(s3_key: str, data: bytes, content_type: str = "image/jpeg") -> dict | None:
    """
    Upload an object to S3, or save to local filesystem if S3 is not configured.
    Returns response metadata dict (S3) or {"local": path} (local).
    """
    client = get_s3_client()
    if client is None:
        # Fall back to local filesystem
        return _save_local(s3_key, data)
    try:
        response = client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=data,
            ContentType=content_type,
        )
        logger.info(f"Uploaded S3 object: {s3_key} ({len(data)} bytes)")
        return response
    except Exception as e:
        logger.warning(f"Failed to upload S3 object {s3_key}: {e}")
        raise


def _save_local(s3_key: str, data: bytes) -> dict:
    """Save file to local avatar directory when S3 is not configured."""
    local_dir = Path(settings.AVATAR_LOCAL_DIR)
    local_path = local_dir / s3_key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    logger.info(f"Saved locally: {local_path} ({len(data)} bytes)")
    return {"local": str(local_path)}


def delete_s3_object(s3_key: str) -> bool:
    """
    Deletes an object from S3. Returns True on success.
    No-op if S3 is not configured.
    """
    client = get_s3_client()
    if client is None:
        logger.info(f"S3 not configured, skipping deletion of {s3_key}")
        return False
    try:
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        logger.info(f"Deleted S3 object: {s3_key}")
        return True
    except Exception as e:
        logger.warning(f"Failed to delete S3 object {s3_key}: {e}")
        return False
