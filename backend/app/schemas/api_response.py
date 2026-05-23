"""
Standardized API response envelope for the public API.

All public endpoints return responses wrapped in ApiResponse or ApiErrorResponse.
Existing internal/frontend endpoints are NOT affected.
"""

import time
from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

from app.core.config import settings

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int = Field(description="Current page number (1-indexed)")
    per_page: int = Field(description="Items per page")
    total: int = Field(description="Total number of items")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")


class ApiMeta(BaseModel):
    pagination: Optional[PaginationMeta] = None
    query_time_ms: Optional[float] = Field(
        None, description="Query execution time in milliseconds"
    )
    api_version: str = Field(default_factory=lambda: settings.API_VERSION)
    data_version: str = Field(default_factory=lambda: settings.DATA_VERSION)
    auth_method: Optional[str] = Field(
        None, description="Authentication method used: jwt, api_key, or session"
    )


class ApiResponse(BaseModel, Generic[T]):
    status: str = "success"
    data: T
    meta: Optional[ApiMeta] = None
    request_id: str = Field(description="Unique request identifier for tracing")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Server timestamp in ISO 8601 format",
    )


class ApiErrorResponse(BaseModel):
    status: str = "error"
    error_code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error description")
    details: Optional[Any] = Field(
        None, description="Additional error context if available"
    )
    request_id: str = Field(description="Unique request identifier for tracing")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


def build_pagination_meta(
    *, page: int, per_page: int, total: int
) -> PaginationMeta:
    total_pages = max(1, (total + per_page - 1) // per_page)
    return PaginationMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
    )


def wrap_response(
    *,
    data: Any,
    request_id: str,
    start_time: Optional[float] = None,
    pagination: Optional[PaginationMeta] = None,
    auth_method: Optional[str] = None,
) -> dict:
    query_time_ms = None
    if start_time is not None:
        query_time_ms = round((time.time() - start_time) * 1000, 2)

    meta = ApiMeta(
        pagination=pagination,
        query_time_ms=query_time_ms,
        auth_method=auth_method,
    )

    return ApiResponse(
        data=data,
        meta=meta,
        request_id=request_id,
    ).model_dump(mode="json")


class ApiListResponse(BaseModel):
    """Response envelope for list endpoints (used for OpenAPI docs)."""
    status: str = "success"
    data: list[Any] = Field(description="List of result items")
    meta: Optional[ApiMeta] = None
    request_id: str = Field(description="Unique request identifier for tracing")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": [
                        {
                            "serviceId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "name": "John Doe",
                            "e164": "+14155551234",
                            "about": "Hey there! I am using Signal.",
                            "groupCount": 5,
                            "username": "johndoe.01",
                            "hasAvatar": True,
                        }
                    ],
                    "meta": {
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 142,
                            "total_pages": 8,
                            "has_next": True,
                        },
                        "query_time_ms": 23.4,
                        "api_version": "1.0",
                        "data_version": "1.0",
                        "auth_method": "api_key",
                    },
                    "request_id": "req_7f3a9b2c",
                    "timestamp": "2026-04-01T12:30:00Z",
                }
            ]
        }
    }


class ApiObjectResponse(BaseModel):
    """Response envelope for single-object endpoints (used for OpenAPI docs)."""
    status: str = "success"
    data: Any = Field(description="Response data object")
    meta: Optional[ApiMeta] = None
    request_id: str = Field(description="Unique request identifier for tracing")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "serviceId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "name": "John Doe",
                        "e164": "+14155551234",
                        "about": "Hey there! I am using Signal.",
                        "groupCount": 5,
                        "username": "johndoe.01",
                        "hasAvatar": True,
                        "groups": [
                            {
                                "groupId": "group_abc123",
                                "groupName": "Project Team",
                                "memberCount": 12,
                            }
                        ],
                    },
                    "meta": {
                        "query_time_ms": 8.1,
                        "api_version": "1.0",
                        "data_version": "1.0",
                        "auth_method": "api_key",
                    },
                    "request_id": "req_7f3a9b2c",
                    "timestamp": "2026-04-01T12:30:00Z",
                }
            ]
        }
    }


def wrap_error(
    *,
    error_code: str,
    message: str,
    request_id: str,
    details: Any = None,
) -> dict:
    return ApiErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        request_id=request_id,
    ).model_dump(mode="json")
