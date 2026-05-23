from datetime import timedelta

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.schemas.app_models import AppUser
from app.db.session import get_db
from app.controllers.auth_controller import AuthController
from app.schemas.auth_models import AuthUserResponse, SetApiPasswordRequest, PasswordTokenRequest
from app.core.logging import logger

router = APIRouter()


def _maybe_sync_subscription(current_user: AppUser, db: Session) -> None:
    """Sync subscription status from Stripe to catch missed webhooks (activations and cancellations)."""
    sub = current_user.subscription
    local_status = sub.status if sub else None

    logger.info(
        f"[SubscriptionSync] user={current_user.email} "
        f"local_status={local_status} is_superuser={current_user.is_superuser}"
    )

    if not current_user.is_superuser:
        # Always sync from Stripe so cancelled subscriptions (missed webhooks) are reflected locally.
        logger.info(f"[SubscriptionSync] Triggering Stripe fallback for user={current_user.email}")
        from app.utils.stripe_utils import sync_subscription_from_stripe
        synced = sync_subscription_from_stripe(db, current_user)
        logger.info(f"[SubscriptionSync] Stripe fallback result: synced={synced} user={current_user.email}")
        db.refresh(current_user)
        logger.info(f"[SubscriptionSync] After refresh: status={current_user.subscription.status if current_user.subscription else None}")


@router.get("/me", response_model=AuthUserResponse)
def read_users_me(
    current_user: AppUser = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user.
    """
    try:
        _maybe_sync_subscription(current_user, db)
        return AuthController.get_me(current_user)
    except Exception as e:
        logger.error(f"Error checking auth status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/token")
def get_jwt_token(
    current_user: AppUser = Depends(deps.get_current_user),
):
    """
    Issue a short-lived JWT for header-based (Bearer) authentication.
    Authenticate first via cookie session, then use the returned token
    in the Authorization: Bearer <token> header for programmatic access.
    """
    token = security.create_access_token(
        subject=current_user.id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/password-token")
def get_jwt_from_password(body: PasswordTokenRequest, db: Session = Depends(get_db)):
    """
    Exchange email + API password for a short-lived JWT.
    Intended for scripted/programmatic access by paid users.
    """
    user = db.query(AppUser).filter(AppUser.email == body.email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.api_password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No API password set. Create one from the API documentation page.",
        )
    if not _bcrypt.checkpw(body.password.encode(), user.api_password_hash.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = security.create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/set-api-password", status_code=204)
def set_api_password(
    body: SetApiPasswordRequest,
    current_user: AppUser = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
):
    """Set or reset the API access password for the current user."""
    hashed = _bcrypt.hashpw(body.password.encode(), _bcrypt.gensalt()).decode()
    current_user.api_password_hash = hashed
    db.commit()


@router.post("/admin/set-user-api-password", status_code=204)
def admin_set_user_api_password(
    body: SetApiPasswordRequest,
    email: str,
    current_user: AppUser = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Admin-only: set the API password for any user by email."""
    target = db.query(AppUser).filter(AppUser.email == email).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    hashed = _bcrypt.hashpw(body.password.encode(), _bcrypt.gensalt()).decode()
    target.api_password_hash = hashed
    db.commit()


@router.delete("/api-password", status_code=204)
def remove_api_password(
    current_user: AppUser = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the API access password for the current user."""
    current_user.api_password_hash = None
    db.commit()


@router.get("/api-password-status")
def get_api_password_status(current_user: AppUser = Depends(deps.get_current_user)):
    """Check whether the current user has an API password set."""
    return {"has_api_password": current_user.api_password_hash is not None}


@router.get("/check-auth", response_model=AuthUserResponse)
def check_auth(
    current_user: AppUser = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check auth status (Proxy for /me).
    """
    _maybe_sync_subscription(current_user, db)
    return AuthController.get_me(current_user)
