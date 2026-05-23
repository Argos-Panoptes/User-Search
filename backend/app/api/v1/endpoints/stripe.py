from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from app.api import deps
from app.db.schemas.app_models import AppUser
from app.utils import stripe_utils
from app.db.session import get_db

router = APIRouter()


from pydantic import BaseModel


class CheckoutSessionRequest(BaseModel):
    has_trial: bool = True


@router.post("/create-checkout-session")
def create_checkout_session(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(deps.get_current_user),
):
    if current_user.is_superuser:
        raise HTTPException(status_code=400, detail="Admins do not need a subscription")
    try:
        url = stripe_utils.create_checkout_session(db, current_user)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create-portal-session")
def create_portal_session(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(deps.get_current_user),
):
    try:
        url = stripe_utils.create_portal_session(current_user)
        return {"url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to create portal session")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db),
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()

    try:
        stripe_utils.handle_webhook_event(db, payload, stripe_signature)
    except Exception as e:
        # Stripe expects 200 even if we fail to process, otherwise it retries.
        # But if signature is bad, 400 is appropriate.
        # If payload is valid but internal logic fails, we might still want to return 200
        # but log error, OR return 500 to trigger retry.
        # Given we want robustness, let's bubble up for retry on internal errors,
        # but handle known errors gracefully.
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success"}


@router.get("/status")
def get_subscription_status(
    current_user: AppUser = Depends(deps.get_current_user),
):
    # This is just a convenience to peek at DB status
    if current_user.subscription:
        return {
            "is_active": current_user.subscription.status == "active",
            "status": current_user.subscription.status,
            "current_period_end": current_user.subscription.current_period_end,
        }
    return {"is_active": False, "status": "none"}
