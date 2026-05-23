from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api import deps
from app.schemas.api_models import (
    UserMetadataDTO,
    UserDetailDTO,
    UserLookupRequest,
    UserHistoryMembershipRequest,
    UserSearchRequest,
    PaginatedResponse,
    PaginatedMeta,
)
from app.controllers.user_controller import UserController
from app.core.logging import logger

router = APIRouter()


@router.post("/users/export")
def export_users(
    request: UserSearchRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        csv_output = UserController.export_users_csv(
            db=db,
            q=request.q,
            service_id=request.service_id,
            name=request.name,
            username=request.username,
            min_group_count=request.min_group_count,
            max_group_count=request.max_group_count,
            e164=request.e164,
            about=request.about,
            is_admin=request.is_admin,
            has_phone=request.has_phone,
            has_avatar=request.has_avatar,
            limit=250,
            offset=0,
        )
        return StreamingResponse(
            csv_output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=user_export.csv"},
        )
    except Exception as e:
        logger.error(f"Error exporting users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/search", response_model=PaginatedResponse[UserMetadataDTO])
def search_users(
    request: UserSearchRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        items = UserController.search_users(
            db=db,
            q=request.q,
            service_id=request.service_id,
            name=request.name,
            group_name=request.group_name,
            group_id=request.group_id,
            username=request.username,
            min_group_count=request.min_group_count,
            max_group_count=request.max_group_count,
            e164=request.e164,
            about=request.about,
            is_admin=request.is_admin,
            has_phone=request.has_phone,
            has_avatar=request.has_avatar,
            sort_by=request.sort_by,
            limit=request.limit,
            offset=request.offset,
        )
        return PaginatedResponse(
            data=items,
            meta=PaginatedMeta(limit=request.limit, offset=request.offset, count=len(items)),
        )
    except Exception as e:
        logger.error(f"Error searching users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/users/{service_id}", response_model=UserDetailDTO)
def get_user_details(
    service_id: str,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        user = UserController.get_user(db, service_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/details", response_model=UserDetailDTO)
def get_user_details_post(
    request: UserLookupRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        user = UserController.get_user(db, request.serviceId)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user details (POST): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/timeline")
def get_user_timeline_endpoint(
    request: UserLookupRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    """
    Fetches the lightweight timeline (ledger) for a user.
    """
    try:
        return UserController.get_user_timeline(
            db, request.serviceId, limit=request.limit, offset=request.offset
        )
    except Exception as e:
        logger.error(f"Error fetching user timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/history/profile")
def get_user_profile_history_endpoint(
    request: UserLookupRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    """
    Fetches the full profile history snapshots.
    """
    try:
        return UserController.get_profile_history(db, request.serviceId)
    except Exception as e:
        logger.error(f"Error fetching profile history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/history/memberships")
def get_user_membership_history_endpoint(
    request: UserLookupRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    """
    Fetches the membership history intervals.
    """
    try:
        return UserController.get_membership_history(db, request.serviceId)
    except Exception as e:
        logger.error(f"Error fetching membership history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/history-memberships")
def get_user_history_memberships(
    request: UserHistoryMembershipRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    """
    Fetches the memberships a user had at a specific point in time.
    """
    try:
        return UserController.get_user_memberships_at_timestamp(
            db, request.serviceId, request.timestamp
        )
    except Exception as e:
        logger.error(f"Error fetching user history memberships: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/users/{service_id}/timeline/{timeline_id}/membership")
def get_user_membership_changes(
    service_id: str,
    timeline_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        return UserController.get_membership_changes(db, timeline_id)
    except Exception as e:
        logger.error(f"Error fetching user membership changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
