"""
Request ID middleware - assigns a unique ID to every request for tracing.
Also logs API key requests to the api_request_logs table.
"""

import time
import uuid

from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import logger


def _log_api_request(
    api_key_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    response_time_ms: int,
    user_agent: str,
):
    """Insert a row into api_request_logs (runs as a background task)."""
    try:
        from app.db.session import SessionLocal
        from app.db.schemas.api_key_models import ApiRequestLog

        db = SessionLocal()
        try:
            log = ApiRequestLog(
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=response_time_ms,
                user_agent=user_agent,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to log API request: {e}")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.start_time = time.time()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        # Log API key requests in background (non-blocking)
        api_key_id = getattr(request.state, "api_key_id", None)
        if api_key_id:
            response_time_ms = round((time.time() - request.state.start_time) * 1000)
            response.background = BackgroundTask(
                _log_api_request,
                api_key_id=api_key_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                user_agent=request.headers.get("user-agent", ""),
            )

        return response
