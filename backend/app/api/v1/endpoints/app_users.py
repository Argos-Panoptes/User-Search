from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.controllers.auth_controller import AuthController
from app.schemas.auth_models import UserResponse

router = APIRouter()


@router.get("/{user_id}", response_model=UserResponse)
def get_user_details(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_superuser),
):
    """
    Get full details for a specific AppUser by ID.
    Restricted to Superusers.
    """
    user = AuthController.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
