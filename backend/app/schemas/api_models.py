from pydantic import BaseModel, field_validator
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")


class PaginatedMeta(BaseModel):
    limit: int
    offset: int
    count: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    meta: PaginatedMeta


class IngestRequest(BaseModel):
    file_path: Optional[str] = None
    upload_id: Optional[str] = None  # Added support for upload_id


class UserMetadataDTO(BaseModel):
    id: Optional[int] = None  # Added for primary key access
    serviceId: str
    e164: Optional[str]
    profileName: Optional[str]
    name: Optional[str] = None
    profileFullName: Optional[str] = None
    about: Optional[str] = None
    isAdmin: Optional[bool]
    exportTimestamp: int
    remoteAvatarUrl: Optional[str] = None
    avatarId: Optional[int] = None
    groupMemberships: Optional[list[dict]] = None
    groupCount: Optional[int] = None
    adminGroupCount: Optional[int] = None
    firstObserved: Optional[str] = None
    lastObserved: Optional[str] = None

    class Config:
        from_attributes = True


class UserDetailDTO(UserMetadataDTO):
    profileFamilyName: Optional[str] = None
    activeAt: Optional[int] = None
    capabilities: Optional[str] = None

    # Technical Details
    profileKey: Optional[str] = None
    profileKeyVersion: Optional[str] = None
    profileKeyCredential: Optional[str] = None
    profileKeyCredentialExpiration: Optional[int] = None
    accessKey: Optional[str] = None
    storageVersion: Optional[int] = None
    storageId: Optional[str] = None
    conversationId: Optional[str] = None
    lastUpdatedJobId: Optional[str] = None
    snapshotHash: Optional[str] = None
    profileLastFetchedAt: Optional[int] = None
    verified: Optional[bool] = None
    color: Optional[str] = None
    sharingPhoneNumber: Optional[str] = None

    class Config:
        from_attributes = True
        extra = "ignore"


class GroupMetadataDTO(BaseModel):
    id: Optional[int] = None  # Added for primary key access
    groupId: str
    groupName: Optional[str]
    numberOfMembers: Optional[int]
    description: Optional[str]
    groupLink: Optional[str]
    reconstructedLink: Optional[str] = None
    adminApprovalRequired: Optional[bool]
    firstObserved: Optional[str] = None
    lastObserved: Optional[str] = None

    class Config:
        from_attributes = True


class GroupMemberDTO(BaseModel):
    serviceId: str
    name: Optional[str]
    role: Optional[str]
    profileName: Optional[str]
    avatarId: Optional[int]


class GroupDetailDTO(GroupMetadataDTO):
    retentionPeriod: Optional[str] = None
    publicParams: Optional[str] = None
    masterKey: Optional[str] = None
    inviteLinkPassword: Optional[str] = None
    secretParams: Optional[str] = None
    members: Optional[list[GroupMemberDTO]] = None

    class Config:
        from_attributes = True
        extra = "ignore"


class UserLookupRequest(BaseModel):
    serviceId: str
    limit: int = 10
    offset: int = 0


class GroupLookupRequest(BaseModel):
    groupId: str
    limit: int = 10
    offset: int = 0


class UserHistoryMembershipRequest(BaseModel):
    serviceId: str
    timestamp: float


class GroupHistoryMembershipRequest(BaseModel):
    groupId: str
    timestamp: float


class UserSearchRequest(BaseModel):
    q: Optional[str] = None
    service_id: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    group_name: Optional[str] = None
    group_id: Optional[str | int] = None
    min_group_count: Optional[int] = None
    max_group_count: Optional[int] = None
    e164: Optional[str] = None
    about: Optional[str] = None
    is_admin: Optional[bool] = None
    has_phone: Optional[bool] = None
    has_avatar: Optional[bool] = None
    sort_by: Optional[str] = None
    limit: int = 250
    offset: int = 0


class GroupSearchRequest(BaseModel):
    q: Optional[str] = None
    group_id: Optional[str | int] = None
    group_name: Optional[str] = None
    description: Optional[str] = None
    min_members: Optional[int] = None
    max_members: Optional[int] = None
    limit: int = 250
    offset: int = 0
    sort_by: Optional[str] = None
    retention_period: Optional[str] = None
    admin_approval_required: Optional[bool] = None
    has_link: Optional[bool] = None


# --- Admin Deletion Schemas ---


class DeleteUserRequest(BaseModel):
    service_id: str
    reason: str
    notes: Optional[str] = None


class BulkDeleteRequest(BaseModel):
    service_ids: list[str]
    reason: str
    notes: Optional[str] = None

    @field_validator("service_ids")
    @classmethod
    def limit_batch_size(cls, v: list[str]) -> list[str]:
        if len(v) > 100:
            raise ValueError("Maximum 100 service IDs per batch")
        if len(v) == 0:
            raise ValueError("At least one service ID required")
        return v


class DeleteUserResponse(BaseModel):
    audit_id: int
    service_id: str
    deleted_by: str
    deleted_at: str
    status: str


class BulkDeleteResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[DeleteUserResponse]
    errors: list[dict]


class AuditLogEntry(BaseModel):
    id: int
    service_id: str
    reason: str
    notes: Optional[str] = None
    deleted_by: str
    deleted_at: str
    user_name: Optional[str] = None
    user_e164: Optional[str] = None


class AuditLogResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int


class UserDeletionPreview(BaseModel):
    service_id: str
    name: Optional[str] = None
    e164: Optional[str] = None
    group_count: int = 0
    has_avatar: bool = False
    is_active: bool = True
    already_excluded: bool = False
