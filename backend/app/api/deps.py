import hashlib
from urllib.parse import unquote
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.db.schemas.app_models import AppUser
from app.db.session import get_db
from app.tasks.user_tasks import update_last_login_task
from app.core.logging import logger

from app.db.schemas.auth_tables import (
    Session as AuthSession,
    User as AuthUser,
)
from app.db.schemas.api_key_models import ApiKey


def get_current_user(request: Request, db: Session = Depends(get_db)) -> AppUser:
    """
    Multi-auth dependency.
    Priority: Authorization Bearer JWT -> X-API-Key header -> Cookie session.
    """
    if not settings.ENABLE_AUTH:
        # Ensure the dev user exists in the database
        email = "dev@example.com"
        user = db.query(AppUser).filter(AppUser.email == email).first()
        if not user:
            user = AppUser(
                email=email,
                full_name="Dev User",
                is_active=True,
                is_superuser=True,
                last_login=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    # 1. Check Authorization: Bearer <token> (JWT)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = security.verify_auth_token(token)
        if payload and payload.get("sub"):
            try:
                user = db.query(AppUser).filter(AppUser.id == int(payload["sub"])).first()
            except (ValueError, TypeError):
                user = None
            if user and user.is_active:
                request.state.auth_method = "jwt"
                request.state.auth_identifier = str(user.id)
                request.state.user_rate_limit = user.rate_limit_per_minute
                if user.is_superuser:
                    request.state.auth_method = "internal"
                return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired JWT token",
        )

    # 2. Check X-API-Key header
    api_key_value = request.headers.get("X-API-Key")
    if api_key_value:
        user = _validate_api_key(api_key_value, request, db)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    # 3. Fall back to cookie session
    session_token = request.cookies.get("better-auth.session_token")

    if not session_token:
        session_token = request.cookies.get(settings.AUTH_COOKIE_NAME)

    logger.debug(f"Auth Check - Cookie Token found: {bool(session_token)}")

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # 2. Check session in database
    # Better Auth can store tokens as raw strings or SHA256 hashes.
    # Also, tokens in cookies might be in the format `token.signature`.
    # And tokens might be URL encoded.
    # URL decode if necessary
    decoded_token = unquote(session_token)

    # Get base token and signature
    token_parts = decoded_token.split(".")
    base_token = token_parts[0]
    signature = token_parts[1] if len(token_parts) > 1 else None
    # Verify Signature if secret is provided and signature exists
    if settings.BETTER_AUTH_SECRET and signature:
        import hmac
        import base64

        expected_sig = (
            base64.b64encode(
                hmac.new(
                    settings.BETTER_AUTH_SECRET.encode(),
                    base_token.encode(),
                    hashlib.sha256,
                ).digest()
            )
            .decode()
            .rstrip("=")
        )

        # Clean signature from cookie for comparison (remove padding if needed)
        clean_sig = signature.rstrip("=")

        if not hmac.compare_digest(expected_sig, clean_sig):
            logger.warning(f"Auth Check - Invalid signature suffix for token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
            )

    hashed_token = hashlib.sha256(base_token.encode()).hexdigest()

    auth_session = (
        db.query(AuthSession)
        .filter(
            (AuthSession.token == base_token)
            | (AuthSession.token == hashed_token)
            | (AuthSession.token == decoded_token)
            | (AuthSession.token == session_token)
        )
        .first()
    )

    if not auth_session:
        logger.warning(
            f"Auth Check - No session found in DB for token: {session_token[:10]}... (also tried hash: {hashed_token[:10]}...)"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    now = datetime.now(timezone.utc)
    # Ensure both are offset-aware for comparison
    expires_at = auth_session.expiresAt
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        logger.warning(f"Auth Check - Session expired: {expires_at} vs {now}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # 3. Get Better Auth user
    auth_user = db.query(AuthUser).filter(AuthUser.id == auth_session.userId).first()
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    email = auth_user.email
    domain = email.split("@")[1] if "@" in email else ""
    is_whitelisted = domain in settings.WHITELISTED_DOMAINS

    # 4. Sync with AppUser using Better Auth ID mapping
    user = db.query(AppUser).filter(AppUser.auth_user_id == auth_user.id).first()

    # Check by email as fallback (migration/bridge case)
    if not user:
        user = db.query(AppUser).filter(AppUser.email == email).first()
        if user:
            # Link legacy user to Better Auth ID
            user.auth_user_id = auth_user.id
            db.commit()
            db.refresh(user)

    if not user:
        user = AppUser(
            auth_user_id=auth_user.id,
            email=email,
            full_name=auth_user.name or "",
            picture=auth_user.image or "",
            is_active=True,
            is_superuser=is_whitelisted,
            last_login=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update details and sync role/customerId
        is_changed = False
        if user.full_name != auth_user.name:
            user.full_name = auth_user.name
            is_changed = True
        if user.picture != auth_user.image:
            user.picture = auth_user.image
            is_changed = True

        # Sync role from Better Auth metadata if present
        if (
            hasattr(auth_user, "role")
            and auth_user.role
            and user.role != auth_user.role
        ):
            user.role = auth_user.role
            is_changed = True

        if is_whitelisted and not user.is_superuser:
            user.is_superuser = True
            is_changed = True

        if is_changed:
            user.last_login = datetime.now(timezone.utc)
            db.commit()
            db.refresh(user)
        else:
            # Update last login if more than 15 mins
            now = datetime.now(timezone.utc)
            if (
                not user.last_login
                or (now - user.last_login.astimezone(timezone.utc)).total_seconds()
                > 900
            ):
                update_last_login_task.delay(user.id, now.timestamp())

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Store Better Auth User ID for subscription check
    user._auth_user_id = auth_user.id
    return user


def get_current_active_superuser(
    current_user: AppUser = Depends(get_current_user),
) -> AppUser:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


def get_current_subscribed_user(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppUser:
    """
    Verify that the user is either an admin or has an active subscription.
    Always syncs from Stripe so missed webhooks (including cancellations) are caught.
    """
    if current_user.is_superuser:
        return current_user

    from app.utils.stripe_utils import sync_subscription_from_stripe
    sync_subscription_from_stripe(db, current_user)
    db.refresh(current_user)

    is_active = (
        current_user.subscription
        and current_user.subscription.status in ("active", "trialing")
    )

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An active subscription is required to access this resource.",
        )

    return current_user



def _validate_api_key(raw_key: str, request: Request, db: Session) -> AppUser | None:
    """
    Validate an API key in format usk_{key_id}.{secret}.
    Returns the associated AppUser or None.
    """
    import bcrypt as _bcrypt

    parts = raw_key.split(".", 1)
    if len(parts) != 2:
        return None

    key_id_part, secret = parts
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_id == key_id_part, ApiKey.is_active == True)
        .first()
    )
    if not api_key:
        return None

    # Check expiration
    if api_key.expires_at:
        now = datetime.now(timezone.utc)
        expires = api_key.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            return None

    # Verify secret against stored hash
    if not _bcrypt.checkpw(secret.encode(), api_key.key_hash.encode()):
        return None

    # Check allowed endpoints — patterns are full path prefixes e.g. "/v1/users"
    if api_key.allowed_endpoints:
        path = request.url.path
        if not any(path.startswith(ep) for ep in api_key.allowed_endpoints):
            return None

    # Enforce per-key rate limit using Redis fixed-window counter
    quota = api_key.quota_limit or settings.DEFAULT_API_KEY_QUOTA
    try:
        import redis as _redis
        _r = _redis.from_url(settings.RATE_LIMIT_REDIS_URL, decode_responses=True)
        rl_key = f"rate_limit:api_key:{api_key.key_id}"
        count = _r.incr(rl_key)
        if count == 1:
            _r.expire(rl_key, 60)
        if count > quota:
            ttl = _r.ttl(rl_key)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
                headers={"Retry-After": str(ttl)},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Rate limit check failed for key {api_key.key_id}: {e}")

    # Update last_used_at and request_count
    api_key.last_used_at = datetime.now(timezone.utc)
    api_key.request_count = (api_key.request_count or 0) + 1
    db.commit()

    # Get the user who owns this key
    user = db.query(AppUser).filter(AppUser.id == api_key.created_by_id).first()
    if not user or not user.is_active:
        return None

    # API keys are for admin/B2B use only
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API keys are restricted to admin users. Use JWT Bearer auth for paid-user access.",
        )

    request.state.auth_method = "api_key"
    request.state.auth_identifier = api_key.key_id
    request.state.api_key_quota = api_key.quota_limit
    request.state.api_key_id = api_key.key_id
    request.state.user_rate_limit = user.rate_limit_per_minute

    return user
