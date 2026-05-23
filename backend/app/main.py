import copy
import json as _json
import re as _re
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager
from app.core.logging import logger
from app.api.v1.endpoints import (
    auth,
    ingestion,
    users,
    groups,
    upload,
    jobs,
    media,
    stripe,
    app_users,
    admin,
    docs,
    internal,
    user_api_keys,
    admin_api_keys,
    admin_monitoring,
)
from app.db.session import get_db
from sqlalchemy.orm import Session
from typing import Dict, Any

# Tables and Models imported for registration when using create_all (now in init_db.py)
from app.init_db import init_db
import sys


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting...")
    try:
        # Initial data ingestion logic moved to app/init_db.py
        # to avoid race conditions with multiple workers
        if "--reload" in sys.argv:
            logger.info("Local reload detected. Initializing database and data...")
            init_db()

    except Exception as e:
        logger.error(f"Error during DB initialization on startup: {e}")
    yield
    logger.info("Application shutdown.")


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Your API key (format: usk_xxxx.secret)")

app = FastAPI(
    title="User Search API",
    description=(
        "REST API for Signal user and group search.\n\n"
        "## Authentication\n\n"
        "Public API endpoints support three authentication methods:\n\n"
        "| Method | Header | Format |\n"
        "|--------|--------|--------|\n"
        "| **API Key** | `X-API-Key` | `usk_xxxx.your_secret_key` |\n"
        "| **JWT Bearer** | `Authorization` | `Bearer <token>` |\n"
        "| **Session Cookie** | *(automatic)* | Browser session |\n\n"
        "To try endpoints below, click **Authorize** and enter your API key.\n\n"
        "---\n\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
    root_path="/app/api",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "docExpansion": "list",
        "filter": True,
        "tryItOutEnabled": True,
    },
    openapi_tags=[
        {"name": "API Keys - User", "description": "Self-service API key management"},
        {"name": "Internal", "description": "Telchines ingestion internal endpoints"},
        {"name": "Admin - API Keys", "description": "Admin API key management"},
        {
            "name": "Admin - Monitoring",
            "description": "System monitoring and usage stats",
        },
        {"name": "Authentication", "description": "Auth status and session management"},
        {"name": "Users", "description": "Internal user search endpoints (GUI)"},
        {"name": "Groups", "description": "Internal group search endpoints (GUI)"},
        {"name": "Admin", "description": "Admin operations (deletion, settings)"},
    ],
)

# Middleware (order matters: first added = outermost)
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.add_middleware(RequestIdMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    components: Dict[str, str] = {}
    status = "ok"

    # Check Database
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        components["db"] = "ok"
    except Exception as e:
        logger.error(f"Health check - DB failure: {str(e)}")
        status = "error"
        components["db"] = "error"

    # Check OpenSearch
    try:
        import requests
        from app.core.config import settings

        response = requests.get(f"{settings.OPENSEARCH_URL}/_cluster/health", timeout=2)
        if response.status_code == 200:
            components["opensearch"] = "ok"
        else:
            components["opensearch"] = "error"
            status = "error"
    except Exception as e:
        logger.error(f"Health check - OpenSearch failure: {str(e)}")
        status = "error"
        components["opensearch"] = "error"

    if status == "error":
        from fastapi import Response

        return Response(content="Service Unavailable", status_code=503)

    return {"status": status, "components": components}


from app.api.deps import (
    get_current_user,
    get_current_active_superuser,
    get_current_subscribed_user,
)

# Auth Router
app.include_router(auth.router, prefix="/v1/auth", tags=["Authentication"])
app.include_router(
    ingestion.router,
    prefix="/v1",
    tags=["Ingestion"],
    dependencies=[Depends(get_current_active_superuser)],
)
app.include_router(
    users.router,
    prefix="/v1",
    tags=["Users"],
    dependencies=[Depends(get_current_subscribed_user)],
)
app.include_router(
    groups.router,
    prefix="/v1",
    tags=["Groups"],
    dependencies=[Depends(get_current_subscribed_user)],
)
app.include_router(
    upload.router,
    prefix="/v1",
    tags=["Uploads"],
    dependencies=[Depends(get_current_active_superuser)],
)
app.include_router(
    media.router,
    prefix="/v1",
    tags=["Media"],
    dependencies=[Depends(get_current_subscribed_user)],
)
app.include_router(
    jobs.router,
    prefix="/v1/jobs",
    tags=["Jobs"],
    dependencies=[Depends(get_current_active_superuser)],
)
app.include_router(
    stripe.router,
    prefix="/v1/stripe",
    tags=["Stripe"],
)
app.include_router(
    app_users.router,
    prefix="/v1/app-users",
    tags=["App Users"],
    dependencies=[Depends(get_current_active_superuser)],
)
app.include_router(
    docs.router,
    prefix="/v1/docs",
    tags=["Documentation"],
    dependencies=[Depends(get_current_user)],
)

app.include_router(
    admin.router,
    prefix="/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_active_superuser)],
)
# app.include_router(logs.router, prefix="/v1/logs", tags=["Logs"]) # Deprecated in favor of job logs

# --- Internal Endpoints (Telchines, superuser only, no rate limit) ---
app.include_router(
    internal.router,
    prefix="/v1/internal",
    tags=["Internal"],
    dependencies=[Depends(get_current_active_superuser)],
)

# --- User API Keys (admin only — API keys are for B2B/internal use) ---
app.include_router(
    user_api_keys.router,
    prefix="/v1/api-keys",
    tags=["API Keys - User"],
    dependencies=[Depends(get_current_active_superuser)],
)

# --- Admin API Key Management ---
app.include_router(
    admin_api_keys.router,
    prefix="/v1/admin/api-keys",
    tags=["Admin - API Keys"],
    dependencies=[Depends(get_current_active_superuser)],
)

# --- Admin Monitoring ---
app.include_router(
    admin_monitoring.router,
    prefix="/v1/admin/monitoring",
    tags=["Admin - Monitoring"],
    dependencies=[Depends(get_current_active_superuser)],
)

# Removed temporary check-auth endpoint. It is now in app/api/v1/endpoints/auth.py

# --- Role-filtered OpenAPI docs ---
ADMIN_TAGS = {
    "Ingestion",
    "Uploads",
    "Jobs",
    "App Users",
    "Admin",
    "Internal",
    "Admin - API Keys",
    "Admin - Monitoring",
    "Stripe",
}


def _ensure_security_schemes(schema: dict) -> dict:
    """Inject API Key and Bearer security schemes into the OpenAPI spec."""
    if "components" not in schema:
        schema["components"] = {}
    if "securitySchemes" not in schema["components"]:
        schema["components"]["securitySchemes"] = {}
    schema["components"]["securitySchemes"]["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Your API key (format: usk_xxxx.secret)",
    }
    schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT Bearer token",
    }
    schema["security"] = [{"ApiKeyAuth": []}, {"BearerAuth": []}]
    return schema


def _get_filtered_openapi(is_superuser: bool) -> dict:
    """Return the full schema for admins, or a filtered copy for regular users."""
    full = _ensure_security_schemes(app.openapi())
    if is_superuser:
        return full

    filtered = copy.deepcopy(full)

    # Remove admin tags from the tag list
    if "tags" in filtered:
        filtered["tags"] = [t for t in filtered["tags"] if t.get("name") not in ADMIN_TAGS]

    # Remove paths whose operations are exclusively under admin tags
    paths_to_remove = []
    for path, methods in filtered.get("paths", {}).items():
        for method, operation in list(methods.items()):
            if not isinstance(operation, dict):
                continue
            tags = set(operation.get("tags", []))
            if tags and tags.issubset(ADMIN_TAGS):
                del methods[method]
        # If no methods remain after filtering, remove the path
        if not any(isinstance(v, dict) for v in methods.values()):
            paths_to_remove.append(path)
    for p in paths_to_remove:
        del filtered["paths"][p]

    # Remove schemas only referenced by admin endpoints
    # Collect all $ref values from remaining paths
    remaining_refs = set()
    paths_json = _json.dumps(filtered.get("paths", {}))
    for ref_match in _re.finditer(r'"\$ref"\s*:\s*"#/components/schemas/([^"]+)"', paths_json):
        remaining_refs.add(ref_match.group(1))

    # Also collect refs from schemas that are themselves referenced (transitive)
    changed = True
    schemas = filtered.get("components", {}).get("schemas", {})
    while changed:
        changed = False
        for name in list(remaining_refs):
            if name in schemas:
                schema_json = _json.dumps(schemas[name])
                for ref_match in _re.finditer(r'"\$ref"\s*:\s*"#/components/schemas/([^"]+)"', schema_json):
                    child = ref_match.group(1)
                    if child not in remaining_refs:
                        remaining_refs.add(child)
                        changed = True

    # Keep only referenced schemas + security schemes
    for schema_name in list(schemas.keys()):
        if schema_name not in remaining_refs:
            del schemas[schema_name]

    # Non-admin users authenticate via JWT Bearer only — hide API key auth
    sec_schemes = filtered.get("components", {}).get("securitySchemes", {})
    sec_schemes.pop("ApiKeyAuth", None)
    filtered["security"] = [{"BearerAuth": []}]

    return filtered


def _try_get_current_user(request: Request):
    """Try to resolve the current user from the session; return None on failure."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return get_current_user(request, db)
    except Exception:
        return None
    finally:
        db.close()


@app.get("/v1/openapi.json", include_in_schema=False)
async def custom_openapi_json(request: Request):
    user = _try_get_current_user(request)
    is_super = user.is_superuser if user else False
    return JSONResponse(_get_filtered_openapi(is_super))


@app.get("/v1/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/app/api/v1/openapi.json",
        title=app.title + " - Docs",
        swagger_ui_parameters=app.swagger_ui_parameters,
    )



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
