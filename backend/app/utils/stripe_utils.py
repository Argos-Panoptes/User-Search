import stripe
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json

from app.core.config import settings
from app.db.schemas.app_models import AppUser
from app.db.schemas.stripe_models import Subscription, PaymentTransaction
from app.core.logging import logger

# Initialize Stripe
stripe.api_key = settings.STRIPE_API_KEY


def create_checkout_session(db: Session, user: AppUser) -> str:
    """
    Creates a Stripe Checkout Session for the user.
    Returns the session URL.
    """
    try:
        # Validate Price Type (Defensive check for production)
        try:
            price = stripe.Price.retrieve(settings.STRIPE_PRICE_ID)
            if price.type != "recurring":
                raise ValueError(
                    f"Invalid Price ID '{settings.STRIPE_PRICE_ID}': Expected a recurring price for subscription mode, but got '{price.type}'. "
                    "Please update your STRIPE_PRICE_ID in the environment variables to a recurring price."
                )
        except stripe.StripeError as e:
            logger.error(f"Stripe Price retrieval failed: {e}")
            # Continue anyway, let Session.create fail if Price ID is totally invalid

        session_params = {
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price": settings.STRIPE_PRICE_ID,
                    "quantity": 1,
                },
            ],
            "mode": "subscription",
            "allow_promotion_codes": True,
            "success_url": f"{settings.FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.FRONTEND_URL}/subscription",
            "client_reference_id": str(user.id),
            "customer_email": user.email,
            "metadata": {"user_id": str(user.id)},
        }

        checkout_session = stripe.checkout.Session.create(**session_params)
        return checkout_session.url
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise e


def create_portal_session(user: AppUser) -> str:
    """
    Creates a Stripe Customer Portal session for the user.
    """
    try:
        if not user.subscription or not user.subscription.stripe_customer_id:
            raise ValueError("User has no active subscription or customer ID")

        portal_session = stripe.billing_portal.Session.create(
            customer=user.subscription.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/subscription",
        )
        return portal_session.url
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise e


def handle_webhook_event(db: Session, payload: bytes, sig_header: str):
    """
    Verifies and handles Stripe webhook events.
    Logs every event to PaymentTransaction.
    """
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid payload: {e}")
        raise e
    except stripe.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid signature: {e}")
        raise e

    # ALWAYS log the transaction/event for audit
    _log_stripe_event(db, event)

    # Handle specific events
    event_type = event["type"]
    data_object = event["data"]["object"]

    logger.info(f"Processing Stripe event: {event_type}")

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db, data_object)
    elif event_type == "invoice.payment_succeeded":
        _handle_invoice_payment_succeeded(db, data_object)
    elif event_type == "customer.subscription.created":
        _handle_subscription_created(db, data_object)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(db, data_object)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db, data_object)

    return {"status": "success"}


def _handle_subscription_created(db: Session, subscription_obj):
    user_id = _resolve_user_id(db, subscription_obj)
    if user_id:
        user = db.query(AppUser).filter(AppUser.id == user_id).first()
        if user:
            _upsert_subscription(db, user, subscription_obj)


def _log_stripe_event(db: Session, event):
    """
    Logs the raw event to PaymentTransaction table with extracted metrics.
    """
    try:
        data_object = event["data"]["object"]
        event_type = event["type"]

        # Extract metrics if available
        amount = None
        if "amount_paid" in data_object:
            amount = data_object.get("amount_paid", 0) / 100.0
        elif "amount_total" in data_object:
            amount = data_object.get("amount_total", 0) / 100.0
        elif "amount" in data_object:
            amount = data_object.get("amount", 0) / 100.0
        elif "plan" in data_object and isinstance(data_object["plan"], dict):
            amount = data_object["plan"].get("amount", 0) / 100.0

        currency = data_object.get("currency")
        if (
            not currency
            and "plan" in data_object
            and isinstance(data_object["plan"], dict)
        ):
            currency = data_object["plan"].get("currency")

        # Resolve user_id
        user_id = _resolve_user_id(db, data_object)

        pt = PaymentTransaction(
            user_id=user_id,
            stripe_transaction_id=event["id"],  # Log the EVENT ID as primary ref
            event_type=event_type,
            status=data_object.get("status", "received"),
            amount=amount,
            currency=currency,
            raw_data=json.loads(str(event)),
            created_at=datetime.now(timezone.utc),
        )
        db.add(pt)
        db.commit()
    except Exception as e:
        logger.error(f"Error logging stripe event: {e}")


def _resolve_user_id(db: Session, data_object) -> int | None:
    """
    Helper to find the local AppUser.id from Stripe data.
    """
    # 1. Try client_reference_id (Checkout Sessions)
    client_ref = data_object.get("client_reference_id")
    if client_ref:
        try:
            return int(client_ref)
        except (ValueError, TypeError):
            return None

    # 2. Try metadata
    metadata = data_object.get("metadata", {})
    if metadata and "user_id" in metadata:
        try:
            return int(metadata["user_id"])
        except (ValueError, TypeError):
            return None

    # 3. Try subscription lookup
    sub_id = data_object.get("subscription")
    if sub_id:
        local_sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == sub_id)
            .first()
        )
        if local_sub:
            return local_sub.user_id

    # 4. Try customer lookup
    cus_id = data_object.get("customer")
    if cus_id:
        local_sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_customer_id == cus_id)
            .first()
        )
        if local_sub:
            return local_sub.user_id

    return None
    # Don't raise here, we want to continue processing if possible,
    # but technically if audit fails we might want to fail hard?
    # For now, log error and continue.


def _handle_checkout_completed(db: Session, session):
    client_reference_id = session.get("client_reference_id")
    # customer_id = session.get("customer") # Unused
    subscription_id = session.get("subscription")

    if not client_reference_id:
        logger.warning("No client_reference_id in checkout session")
        return

    user_id = client_reference_id
    try:
        user_id_int = int(user_id)
        user = db.query(AppUser).filter(AppUser.id == user_id_int).first()
    except (ValueError, TypeError):
        user = None

    if user:
        # Fetch subscription details to get period end
        sub = stripe.Subscription.retrieve(subscription_id)

        _upsert_subscription(db, user, sub)
        # Backfill any invoices that were already paid before the webhook arrived
        _sync_invoices(db, user, sub["id"])


def _handle_invoice_payment_succeeded(db: Session, invoice):
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return

    local_sub = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == subscription_id)
        .first()
    )

    if local_sub:
        # Sync latest status from Stripe (authoritative)
        sub = stripe.Subscription.retrieve(subscription_id)
        _upsert_subscription(db, local_sub.user, sub)
        _log_payment_success(db, local_sub.user_id, invoice)
    else:
        # Race condition: checkout.session.completed not yet processed.
        # Resolve user via customer ID and upsert so nothing is lost.
        user_id = _resolve_user_id(db, invoice)
        if user_id:
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
        else:
            customer_id = invoice.get("customer")
            user = (
                db.query(AppUser)
                .join(Subscription, Subscription.user_id == AppUser.id, isouter=True)
                .filter(Subscription.stripe_customer_id == customer_id)
                .first()
                if customer_id
                else None
            )

        if user:
            sub = stripe.Subscription.retrieve(subscription_id)
            _upsert_subscription(db, user, sub)
            _log_payment_success(db, user.id, invoice)
        else:
            logger.warning(
                f"invoice.payment_succeeded: cannot resolve user for subscription {subscription_id}. "
                "Will be captured on next fallback sync."
            )


def _handle_subscription_updated(db: Session, subscription_obj):
    stripe_sub_id = subscription_obj.get("id")
    local_sub = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == stripe_sub_id)
        .first()
    )

    if local_sub:
        _upsert_subscription(db, local_sub.user, subscription_obj)


def _handle_subscription_deleted(db: Session, subscription_obj):
    stripe_sub_id = subscription_obj.get("id")
    local_sub = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == stripe_sub_id)
        .first()
    )

    if local_sub:
        local_sub.status = "canceled"
        local_sub.cancel_at_period_end = False  # It is done
        db.commit()


def _upsert_subscription(db: Session, user: AppUser, stripe_sub):
    current_period_end = datetime.fromtimestamp(
        stripe_sub["current_period_end"], timezone.utc
    )

    # Check if exists
    sub_record = db.query(Subscription).filter(Subscription.user_id == user.id).first()

    if not sub_record:
        sub_record = Subscription(
            user_id=user.id,
            stripe_subscription_id=stripe_sub["id"],
            stripe_customer_id=stripe_sub["customer"],
            status=stripe_sub["status"],
            current_period_end=current_period_end,
            cancel_at_period_end=stripe_sub["cancel_at_period_end"],
        )
        db.add(sub_record)
    else:
        # Update
        sub_record.stripe_subscription_id = stripe_sub["id"]  # Just in case
        sub_record.status = stripe_sub["status"]
        sub_record.current_period_end = current_period_end
        sub_record.cancel_at_period_end = stripe_sub["cancel_at_period_end"]
        sub_record.updated_at = datetime.now(timezone.utc)

    db.commit()


def _sync_invoices(db: Session, user: AppUser, subscription_id: str) -> None:
    """
    Fetch all paid invoices from Stripe for a subscription and persist any
    that are not already recorded as PaymentTransaction rows.
    """
    try:
        existing_ids = {
            pt.stripe_transaction_id
            for pt in db.query(PaymentTransaction.stripe_transaction_id)
            .filter(PaymentTransaction.user_id == user.id)
            .all()
        }

        invoices = stripe.Invoice.list(subscription=subscription_id, limit=100)
        for invoice in invoices.auto_paging_iter():
            if invoice.get("status") != "paid":
                continue
            invoice_id = invoice.get("id")
            if invoice_id in existing_ids:
                continue
            amount = invoice.get("amount_paid", 0) / 100.0
            currency = invoice.get("currency", "usd")
            created_ts = invoice.get("created")
            created_at = (
                datetime.fromtimestamp(created_ts, timezone.utc)
                if created_ts
                else datetime.now(timezone.utc)
            )
            pt = PaymentTransaction(
                user_id=user.id,
                stripe_transaction_id=invoice_id,
                amount=amount,
                currency=currency,
                status="succeeded",
                event_type="invoice.payment_succeeded",
                raw_data=dict(invoice),
                created_at=created_at,
            )
            db.add(pt)
            print(f"[StripeFallback] Saved invoice {invoice_id} amount=${amount} for user {user.id}")

        db.commit()
    except Exception as e:
        logger.error(f"[StripeFallback] Failed to sync invoices for user {user.id}: {e}", exc_info=True)


def sync_transactions_from_stripe(db: Session, user: AppUser) -> None:
    """
    Sync invoice/payment records for an already-active local subscription.
    Called when the subscription row exists but transaction records may be missing.
    """
    sub = user.subscription
    if not sub or not sub.stripe_subscription_id:
        return
    _sync_invoices(db, user, sub.stripe_subscription_id)


def sync_subscription_from_stripe(db: Session, user: AppUser) -> bool:
    """
    Fallback: query Stripe directly for the latest subscription tied to this user's email.
    Syncs to local DB and returns True if an active/trialing subscription was found.
    Also detects cancellations missed by webhooks and marks the local record + transaction accordingly.
    """
    print(f"[StripeFallback] Querying Stripe for email={user.email}")
    try:
        customers = stripe.Customer.list(email=user.email, limit=5)
        print(f"[StripeFallback] Found {len(customers.data)} customer(s) in Stripe for email={user.email}")

        if not customers or not customers.data:
            return False

        for customer in customers.data:
            print(f"[StripeFallback] Checking customer {customer.id}")
            subscriptions = stripe.Subscription.list(
                customer=customer.id,
                status="all",
                limit=10,
            )

            active_sub = None
            canceled_sub = None

            for sub in subscriptions.auto_paging_iter():
                print(f"[StripeFallback] Found subscription {sub.id} status={sub.status}")
                if sub.status in ("active", "trialing"):
                    active_sub = sub
                    break
                elif sub.status in ("canceled", "incomplete_expired", "unpaid") and canceled_sub is None:
                    canceled_sub = sub

            if active_sub:
                print(f"[StripeFallback] Syncing active subscription {active_sub.id} for user {user.id}")
                _upsert_subscription(db, user, active_sub)
                _sync_invoices(db, user, active_sub.id)
                return True

            if canceled_sub:
                print(f"[StripeFallback] Detected canceled subscription {canceled_sub.id} for user {user.id}")
                _upsert_subscription(db, user, canceled_sub)
                _log_cancellation_transaction(db, user.id, canceled_sub)
                return False

        print(f"[StripeFallback] No subscriptions found for email={user.email}")
        return False
    except stripe.StripeError as e:
        logger.error(f"[StripeFallback] Stripe API error for user {user.id}: {e}")
        return False
    except Exception as e:
        logger.error(f"[StripeFallback] Unexpected error for user {user.id}: {e}", exc_info=True)
        return False


def _log_cancellation_transaction(db: Session, user_id: int, stripe_sub) -> None:
    """
    Log a cancellation event to PaymentTransaction so audits reflect the cancellation.
    Skips if an identical event was already recorded.
    """
    try:
        existing = (
            db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.user_id == user_id,
                PaymentTransaction.stripe_transaction_id == stripe_sub["id"],
                PaymentTransaction.event_type == "customer.subscription.deleted",
            )
            .first()
        )
        if existing:
            return

        pt = PaymentTransaction(
            user_id=user_id,
            stripe_transaction_id=stripe_sub["id"],
            event_type="customer.subscription.deleted",
            status="canceled",
            amount=None,
            currency=None,
            raw_data=dict(stripe_sub),
            created_at=datetime.now(timezone.utc),
        )
        db.add(pt)
        db.commit()
        print(f"[StripeFallback] Logged cancellation transaction for user {user_id} sub {stripe_sub['id']}")
    except Exception as e:
        logger.error(f"[StripeFallback] Failed to log cancellation transaction: {e}", exc_info=True)


def _log_payment_success(db: Session, user_id: int, invoice):
    """
    Log a specific approved payment transaction linked to the user.
    """
    amount = invoice.get("amount_paid", 0) / 100.0  # cents to dollars
    currency = invoice.get("currency", "usd")

    pt = PaymentTransaction(
        user_id=user_id,
        stripe_transaction_id=invoice.get("id"),
        amount=amount,
        currency=currency,
        status="succeeded",
        event_type="invoice_payment",
        raw_data=invoice,
        created_at=datetime.now(timezone.utc),
    )
    db.add(pt)
    db.commit()
