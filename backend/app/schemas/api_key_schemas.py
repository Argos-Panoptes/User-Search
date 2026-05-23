from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name for this API key")
    description: Optional[str] = Field(None, max_length=500)
    expires_in_days: int = Field(
        30, ge=1, le=365, description="Days until expiration"
    )


class ApiKeyAdminCreate(ApiKeyCreate):
    user_id: Optional[int] = Field(None, description="Create key on behalf of this user")
    quota_limit: Optional[int] = Field(None, ge=1, description="Custom requests/minute limit")
    allowed_endpoints: Optional[list[str]] = Field(None, description="Restrict to these endpoint patterns")


class ApiKeyCreatedResponse(BaseModel):
    key_id: str
    raw_key: str = Field(description="Full API key - shown only once")
    name: str
    description: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    quota_limit: Optional[int] = None


class ApiKeyListItem(BaseModel):
    key_id: str
    name: str
    description: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    quota_limit: Optional[int] = None
    request_count: int = 0


class ApiKeyDetail(ApiKeyListItem):
    allowed_endpoints: Optional[list[str]] = None
    metadata_json: Optional[dict[str, Any]] = None
    created_by_id: int


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class ApiKeyAdminUpdate(ApiKeyUpdate):
    is_active: Optional[bool] = None
    quota_limit: Optional[int] = Field(None, ge=1)
    allowed_endpoints: Optional[list[str]] = None
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
