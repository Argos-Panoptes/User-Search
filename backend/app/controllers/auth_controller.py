from app.schemas.auth_models import UserResponse, AuthUserResponse
from app.core.logging import logger


class AuthController:
    @staticmethod
    def get_me(current_user) -> AuthUserResponse:
        logger.info(f"Fetching current user: {current_user.email}")
        sub = current_user.subscription
        sub_status = sub.status if sub else None
        all_transactions = current_user.payment_transactions or []

        # Only surface actual invoice payment rows — exclude raw webhook audit events
        BILLING_EVENT_TYPES = {"invoice_payment", "invoice.payment_succeeded"}
        billing_transactions = [
            t for t in all_transactions
            if t.event_type in BILLING_EVENT_TYPES and t.amount is not None
        ]

        total_spent = sum(float(t.amount) for t in billing_transactions if t.status == "succeeded")
        return AuthUserResponse(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            picture=current_user.picture,
            is_active=current_user.is_active,
            is_superuser=current_user.is_superuser,
            last_login=current_user.last_login,
            subscription_status=sub_status,
            subscription=sub,
            total_spent=total_spent,
            total_payments=len([t for t in billing_transactions if t.status == "succeeded"]),
            payment_transactions=billing_transactions,
        )

    @staticmethod
    def get_user_by_id(db, user_id: int) -> UserResponse | None:
        from app.db.schemas.app_models import AppUser

        user = db.query(AppUser).filter(AppUser.id == user_id).first()
        if user:
            return user
        return None
