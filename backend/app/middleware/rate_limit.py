"""
Rate limiting middleware using slowapi with Redis backend.

Rate limits by auth type:
- JWT Bearer: 100 requests/minute per user
- API Key: 1000 requests/minute per key (or custom quota)
- Cookie/Session: 100 requests/minute per user
- Internal/Superuser: unlimited
"""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.schemas.api_response import wrap_error


def _get_rate_limit_key(request: Request) -> str:
    auth_method = getattr(request.state, "auth_method", None)
    auth_id = getattr(request.state, "auth_identifier", None)

    if auth_method == "internal":
        return ""  # unlimited

    if auth_method and auth_id:
        return f"{auth_method}:{auth_id}"

    # Fallback to IP
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=_get_rate_limit_key,
    storage_uri=settings.RATE_LIMIT_REDIS_URL,
    strategy="fixed-window",
)


def get_dynamic_rate_limit(request: Request) -> str:
    auth_method = getattr(request.state, "auth_method", None)

    if auth_method == "internal":
        return "10000/minute"  # effectively unlimited

    # Check per-user rate limit override (set by admin)
    user_rate_limit = getattr(request.state, "user_rate_limit", None)

    if auth_method == "api_key":
        # Per-key quota takes priority, then per-user limit, then default
        quota = getattr(request.state, "api_key_quota", None)
        if quota:
            return f"{quota}/minute"
        if user_rate_limit:
            return f"{user_rate_limit}/minute"
        return "1000/minute"

    # JWT and cookie/session users — per-user limit or default
    if user_rate_limit:
        return f"{user_rate_limit}/minute"
    return "100/minute"


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    retry_after = getattr(exc, "retry_after", 60)

    body = wrap_error(
        error_code="RATE_LIMIT_EXCEEDED",
        message=f"Rate limit exceeded. Try again in {retry_after} seconds.",
        request_id=request_id,
        details={"retry_after": retry_after},
    )

    return JSONResponse(
        status_code=429,
        content=body,
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(getattr(exc, "limit", "")),
        },
    )
