import logging
from typing import Literal
import uuid

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
import stripe

from bxk_app.authorization import (
    get_authenticated_user,
)
from bxk_app.database import get_db
from bxk_app.db_models.user import User
from bxk_app.services.stripe_billing_service import (
    BillingConfigurationError,
    BillingStateError,
    BillingWebhookConflictError,
    BillingWebhookError,
    billing_status_for_user,
    construct_stripe_event,
    create_checkout_session,
    create_customer_portal_session,
    process_stripe_webhook,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/billing",
    tags=["Billing"],
)


class CheckoutSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interval: Literal["MONTHLY", "ANNUAL"]
    request_token: uuid.UUID


def _database_user(
    authenticated_user: dict,
    session: Session,
) -> User:
    if (
        authenticated_user.get("auth_source")
        != "DATABASE"
        or not authenticated_user.get("user_id")
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Subscription billing requires a "
                "database-backed BXK account."
            ),
        )

    try:
        user_id = uuid.UUID(
            str(authenticated_user["user_id"])
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="BXK authentication required.",
        ) from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="BXK authentication required.",
        )
    return user


def _billing_error(exc: Exception):
    if isinstance(exc, BillingConfigurationError):
        return HTTPException(
            status_code=503,
            detail=str(exc),
        )
    if isinstance(exc, BillingStateError):
        return HTTPException(
            status_code=409,
            detail=str(exc),
        )
    return HTTPException(
        status_code=502,
        detail=(
            "Stripe could not complete the billing "
            "request. Please try again."
        ),
    )


@router.get("/status")
def billing_status(
    request: Request,
    session: Session = Depends(get_db),
):
    authenticated_user = get_authenticated_user(
        request
    )
    user = _database_user(
        authenticated_user,
        session,
    )
    return billing_status_for_user(
        session,
        user,
    )


@router.post("/checkout-session")
def billing_checkout_session(
    request_data: CheckoutSessionRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    authenticated_user = get_authenticated_user(
        request
    )
    user = _database_user(
        authenticated_user,
        session,
    )

    try:
        return create_checkout_session(
            session,
            user=user,
            interval=request_data.interval,
            request_token=str(
                request_data.request_token
            ),
        )
    except (
        BillingConfigurationError,
        BillingStateError,
    ) as exc:
        raise _billing_error(exc) from exc
    except stripe.StripeError as exc:
        logger.exception(
            "Stripe Checkout Session creation failed."
        )
        raise _billing_error(exc) from exc


@router.post("/portal-session")
def billing_portal_session(
    request: Request,
    session: Session = Depends(get_db),
):
    authenticated_user = get_authenticated_user(
        request
    )
    user = _database_user(
        authenticated_user,
        session,
    )

    try:
        return create_customer_portal_session(
            session,
            user=user,
        )
    except (
        BillingConfigurationError,
        BillingStateError,
    ) as exc:
        raise _billing_error(exc) from exc
    except stripe.StripeError as exc:
        logger.exception(
            "Stripe Customer Portal creation failed."
        )
        raise _billing_error(exc) from exc


@router.post("/webhook")
async def stripe_billing_webhook(
    request: Request,
    stripe_signature: str | None = Header(
        default=None,
        alias="Stripe-Signature",
    ),
    session: Session = Depends(get_db),
):
    payload = await request.body()

    try:
        event = construct_stripe_event(
            payload,
            stripe_signature,
        )
        return process_stripe_webhook(
            session,
            event=event,
            payload=payload,
        )
    except BillingConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except BillingWebhookConflictError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except BillingWebhookError as exc:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception:
        session.rollback()
        logger.exception(
            "Stripe webhook processing failed."
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Stripe webhook processing failed."
            ),
        )
