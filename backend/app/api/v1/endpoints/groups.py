from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api import deps
from app.schemas.api_models import (
    GroupMetadataDTO,
    GroupDetailDTO,
    GroupLookupRequest,
    GroupHistoryMembershipRequest,
    GroupSearchRequest,
    UserLookupRequest,
    UserHistoryMembershipRequest,
    UserSearchRequest,
    PaginatedResponse,
    PaginatedMeta,
)
from app.controllers.group_controller import GroupController
from app.core.logging import logger
from app.utils.reconstruct_utils import generate_signal_group_url
from app.ingestion import search_indexer

router = APIRouter()


@router.get("/groups/retention-periods", response_model=List[str])
def get_retention_periods(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        return GroupController.get_retention_periods(db)
    except Exception as e:
        logger.error(f"Error fetching retention periods: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/groups/search", response_model=PaginatedResponse[GroupMetadataDTO])
def search_groups(
    request: GroupSearchRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        items = GroupController.search_groups(
            db,
            request.q,
            request.group_id,
            request.group_name,
            request.description,
            request.min_members,
            request.max_members,
            request.limit,
            request.offset,
            request.sort_by,
            request.retention_period,
            request.admin_approval_required,
            request.has_link,
        )
        return PaginatedResponse(
            data=items,
            meta=PaginatedMeta(limit=request.limit, offset=request.offset, count=len(items)),
        )
    except Exception as e:
        logger.error(f"Error searching groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/groups/{group_id}", response_model=GroupDetailDTO)
def get_group_details(
    group_id: str,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        group = GroupController.get_group(db, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        return group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching group details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/groups/{group_id}/history")
def get_group_history_endpoint(
    group_id: str,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        return GroupController.get_group_history(db, group_id)
    except Exception as e:
        logger.error(f"Error fetching group history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/groups/details", response_model=GroupDetailDTO)
def get_group_details_post(
    request: GroupLookupRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        group = GroupController.get_group(db, request.groupId)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        return group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching group details (POST): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/groups/history")
def get_group_history_post(
    request: GroupLookupRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        return GroupController.get_group_history(db, request.groupId)
    except Exception as e:
        logger.error(f"Error fetching group history (POST): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/groups/history-members")
def get_group_history_members(
    request: GroupHistoryMembershipRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    """
    Fetches the members of a group at a specific point in time.
    """
    try:
        return GroupController.get_group_members_at_timestamp(
            db, request.groupId, request.timestamp
        )
    except Exception as e:
        logger.error(f"Error fetching group history members: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/groups/timeline")
def get_group_timeline_endpoint(
    request: GroupLookupRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        return GroupController.get_group_timeline(
            db, request.groupId, limit=request.limit, offset=request.offset
        )
    except Exception as e:
        logger.error(f"Error fetching group timeline (POST): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/groups/{group_id}/timeline/{timeline_id}/membership")
def get_group_membership_changes(
    group_id: str,
    timeline_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        return GroupController.get_membership_changes(db, timeline_id)
    except Exception as e:
        logger.error(f"Error fetching group membership changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/groups/export")
def export_groups(
    request: GroupSearchRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    try:
        csv_file = GroupController.export_groups_csv(
            db,
            request.q,
            request.group_id,
            request.group_name,
            request.description,
            request.min_members,
            request.max_members,
            250,
            0,
            request.sort_by,
            request.retention_period,
            request.admin_approval_required,
            request.has_link,
        )
        return StreamingResponse(
            iter([csv_file.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=groups_export.csv"},
        )
    except Exception as e:
        logger.error(f"Error exporting groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# @router.post("/groups/{group_id}/reconstruct-link")
# def reconstruct_group_link(
#     group_id: str,
#     db: Session = Depends(deps.get_db),
#     current_user=Depends(deps.get_current_subscribed_user),
# ):
#     try:
#         from app.db.schemas.ingestion_models import GroupMetadata
#
#         db_group = (
#             db.query(GroupMetadata).filter(GroupMetadata.group_id == group_id).first()
#         )
#         if not db_group:
#             raise HTTPException(status_code=404, detail="Group not found in DB")
#
#         if not db_group.master_key or not db_group.invite_link_password:
#             raise HTTPException(
#                 status_code=400,
#                 detail="Group is missing masterKey or inviteLinkPassword. Link cannot be reconstructed.",
#             )
#
#         new_link = generate_signal_group_url(
#             str(db_group.master_key), str(db_group.invite_link_password)
#         )
#
#         db_group.reconstructed_link = new_link
#         db.commit()
#
#         # Update index
#         search_indexer.index_groups_by_ids([db_group.id])  # type: ignore
#
#         return {"status": "success", "reconstructed_link": new_link}
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error reconstructing link: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal Server Error")
