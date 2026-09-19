from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Mapping
import uuid

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import stripe

from bxk_app import config
from bxk_app.db_models.subscription import (
    BillingWebhookEvent,
    SubscriptionPlan,
    SubscriptionProvider,
    SubscriptionStatus,
    UserSubscription,
)
from bxk_app.db_models.user import User, UserRole
from bxk_app.services.subscription_service import (
    ACCESSIBLE_STATUSES,
    evaluate_subscription_access,
    get_user_subscription,
)


SUBSCRIPTION_EVENT_TYPES = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.paused",
    "customer.subscription.resumed",
}

INVOICE_EVENT_TYPES = {
    "invoice.paid",
    "invoice.payment_failed",
}

STRIPE_STATUS_MAP = {
    "incomplete": SubscriptionStatus.INCOMPLETE,
    "incomplete_expired": SubscriptionStatus.CANCELED,
    "trialing": SubscriptionStatus.TRIALING,
    "active": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "paused": SubscriptionStatus.PAUSED,
    "canceled": SubscriptionStatus.CANCELED,
    "unpaid": SubscriptionStatus.UNPAID,
}


class BillingConfigurationError(RuntimeError):
    pass


class BillingStateError(RuntimeError):
    pass


class BillingWebhookError(ValueError):
    pass


class BillingWebhookConflictError(BillingWebhookError):
    pass


def _value(obj: Any, key: str, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value

    for converter_name in (
        "to_dict",
        "to_dict_recursive",
        "_to_dict_recursive",
    ):
        converter = getattr(
            value,
            converter_name,
            None,
        )

        if callable(converter):
            converted = converter()
            if isinstance(converted, dict):
                return converted

    if isinstance(value, Mapping):
        return dict(value)

    raise BillingWebhookError(
        "Stripe event payload is malformed."
    )


def _timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    try:
        return datetime.fromtimestamp(
            int(value),
            tz=timezone.utc,
        )
    except (TypeError, ValueError, OSError):
        return None


def _normalize_datetime(value: datetime | None):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _configured_price_ids() -> set[str]:
    return {
        price_id
        for price_id in (
            config.STRIPE_PRICE_PRO_MONTHLY,
            config.STRIPE_PRICE_PRO_ANNUAL,
        )
        if str(price_id or "").strip()
    }


def billing_configuration_status() -> dict:
    monthly = bool(
        str(
            config.STRIPE_PRICE_PRO_MONTHLY
            or ""
        ).strip()
    )
    annual = bool(
        str(
            config.STRIPE_PRICE_PRO_ANNUAL
            or ""
        ).strip()
    )
    secret_key = bool(
        str(config.STRIPE_SECRET_KEY or "").strip()
    )
    webhook_secret = bool(
        str(
            config.STRIPE_WEBHOOK_SECRET or ""
        ).strip()
    )
    public_url = bool(
        str(config.BXK_PUBLIC_APP_URL or "").strip()
    )
    enabled = bool(config.BXK_BILLING_ENABLED)

    return {
        "enabled": enabled,
        "checkout_configured": bool(
            secret_key
            and public_url
            and (monthly or annual)
        ),
        "webhook_configured": bool(
            secret_key and webhook_secret
        ),
        "portal_configured": bool(
            secret_key and public_url
        ),
        "plans": {
            "MONTHLY": {
                "available": bool(
                    enabled and monthly
                ),
                "plan": "PRO",
            },
            "ANNUAL": {
                "available": bool(
                    enabled and annual
                ),
                "plan": "PRO",
            },
        },
    }


def _require_billing_enabled() -> None:
    if not config.BXK_BILLING_ENABLED:
        raise BillingConfigurationError(
            "BXK subscription billing is not enabled."
        )

    if not str(config.STRIPE_SECRET_KEY or "").strip():
        raise BillingConfigurationError(
            "Stripe billing is not fully configured."
        )


def _price_for_interval(interval: str) -> str:
    normalized = str(interval or "").strip().upper()

    if normalized == "MONTHLY":
        price_id = config.STRIPE_PRICE_PRO_MONTHLY
    elif normalized == "ANNUAL":
        price_id = config.STRIPE_PRICE_PRO_ANNUAL
    else:
        raise BillingStateError(
            "Unsupported billing interval."
        )

    price_id = str(price_id or "").strip()

    if not price_id:
        raise BillingConfigurationError(
            f"The {normalized.lower()} Stripe price "
            "is not configured."
        )

    return price_id


def _stripe_client():
    _require_billing_enabled()
    return stripe.StripeClient(
        config.STRIPE_SECRET_KEY
    )


def _eligible_billing_user(user: User) -> None:
    role = (
        user.role.value
        if isinstance(user.role, UserRole)
        else str(user.role or "").upper()
    )

    if role == UserRole.OWNER.value:
        raise BillingStateError(
            "OWNER accounts already have permanent access."
        )

    if role != UserRole.BETA.value:
        raise BillingStateError(
            "This account is not eligible for a trading "
            "subscription."
        )


def create_checkout_session(
    session: Session,
    *,
    user: User,
    interval: str,
    request_token: str,
    client=None,
) -> dict:
    _require_billing_enabled()
    _eligible_billing_user(user)

    price_id = _price_for_interval(interval)
    normalized_interval = str(interval).upper()
    subscription = get_user_subscription(
        session,
        user.id,
    )

    if (
        subscription is not None
        and subscription.provider
        == SubscriptionProvider.STRIPE
        and subscription.status
        in ACCESSIBLE_STATUSES
    ):
        raise BillingStateError(
            "This account already has an active Stripe "
            "subscription. Use Manage Billing instead."
        )

    public_url = str(
        config.BXK_PUBLIC_APP_URL or ""
    ).strip().rstrip("/")

    if not public_url:
        raise BillingConfigurationError(
            "BXK_PUBLIC_APP_URL is not configured."
        )

    try:
        token = str(uuid.UUID(str(request_token)))
    except (TypeError, ValueError) as exc:
        raise BillingStateError(
            "A valid checkout request token is required."
        ) from exc

    params = {
        "mode": "subscription",
        "line_items": [
            {
                "price": price_id,
                "quantity": 1,
            }
        ],
        "client_reference_id": str(user.id),
        "success_url": (
            f"{public_url}/subscription"
            "?checkout=success"
        ),
        "cancel_url": (
            f"{public_url}/subscription"
            "?checkout=canceled"
        ),
        "metadata": {
            "bxk_user_id": str(user.id),
            "plan_code": SubscriptionPlan.PRO.value,
            "billing_interval": normalized_interval,
            "provider_price_id": price_id,
        },
        "subscription_data": {
            "metadata": {
                "bxk_user_id": str(user.id),
                "plan_code": SubscriptionPlan.PRO.value,
                "billing_interval": normalized_interval,
                "provider_price_id": price_id,
            }
        },
    }

    if (
        subscription is not None
        and subscription.provider_customer_id
    ):
        params["customer"] = (
            subscription.provider_customer_id
        )
    else:
        params["customer_email"] = user.email

    stripe_client = client or _stripe_client()
    result = (
        stripe_client.v1.checkout.sessions.create(
            params,
            options={
                "idempotency_key": (
                    "bxk-checkout:"
                    f"{user.id}:"
                    f"{normalized_interval}:"
                    f"{token}"
                )
            },
        )
    )

    checkout_id = str(
        _value(result, "id", "") or ""
    ).strip()
    checkout_url = str(
        _value(result, "url", "") or ""
    ).strip()

    if not checkout_id or not checkout_url:
        raise BillingStateError(
            "Stripe did not return a usable Checkout "
            "Session."
        )

    return {
        "checkout_session_id": checkout_id,
        "url": checkout_url,
    }


def create_customer_portal_session(
    session: Session,
    *,
    user: User,
    client=None,
) -> dict:
    _require_billing_enabled()
    _eligible_billing_user(user)

    subscription = get_user_subscription(
        session,
        user.id,
    )

    if (
        subscription is None
        or subscription.provider
        != SubscriptionProvider.STRIPE
        or not subscription.provider_customer_id
    ):
        raise BillingStateError(
            "No Stripe billing account is connected to "
            "this BXK account."
        )

    public_url = str(
        config.BXK_PUBLIC_APP_URL or ""
    ).strip().rstrip("/")

    stripe_client = client or _stripe_client()
    result = (
        stripe_client.v1.billing_portal.sessions.create(
            {
                "customer": (
                    subscription.provider_customer_id
                ),
                "return_url": (
                    f"{public_url}/subscription"
                ),
            }
        )
    )

    portal_url = str(
        _value(result, "url", "") or ""
    ).strip()

    if not portal_url:
        raise BillingStateError(
            "Stripe did not return a usable Customer "
            "Portal Session."
        )

    return {"url": portal_url}


def construct_stripe_event(
    payload: bytes,
    signature: str | None,
) -> dict:
    if not config.BXK_BILLING_ENABLED:
        raise BillingConfigurationError(
            "BXK subscription billing is not enabled."
        )

    webhook_secret = str(
        config.STRIPE_WEBHOOK_SECRET or ""
    ).strip()

    if not webhook_secret:
        raise BillingConfigurationError(
            "Stripe webhooks are not configured."
        )

    if not signature:
        raise BillingWebhookError(
            "Stripe-Signature header is required."
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            webhook_secret,
        )
    except (
        ValueError,
        stripe.error.SignatureVerificationError,
    ) as exc:
        raise BillingWebhookError(
            "Stripe webhook signature is invalid."
        ) from exc

    return _as_dict(event)


def _metadata(obj: Any) -> dict:
    value = _value(obj, "metadata", {})
    return value if isinstance(value, Mapping) else {}


def _user_from_id(
    session: Session,
    user_id: Any,
) -> User | None:
    try:
        parsed = uuid.UUID(str(user_id or ""))
    except (TypeError, ValueError):
        return None
    return session.get(User, parsed)


def _find_subscription_record(
    session: Session,
    *,
    user_id: Any = None,
    customer_id: Any = None,
    subscription_id: Any = None,
) -> tuple[User | None, UserSubscription | None]:
    user = _user_from_id(session, user_id)
    record = (
        get_user_subscription(session, user.id)
        if user is not None
        else None
    )

    identifiers = [
        condition
        for condition in (
            (
                UserSubscription
                .provider_subscription_id
                == str(subscription_id)
                if subscription_id
                else None
            ),
            (
                UserSubscription
                .provider_customer_id
                == str(customer_id)
                if customer_id
                else None
            ),
        )
        if condition is not None
    ]

    matched = None
    if identifiers:
        matched = session.scalar(
            select(UserSubscription).where(
                or_(*identifiers)
            )
        )

    if (
        user is not None
        and matched is not None
        and user.id != matched.user_id
    ):
        raise BillingWebhookConflictError(
            "Stripe identifiers are already connected "
            "to another BXK account."
        )

    record = record or matched

    if user is None and record is not None:
        user = session.get(User, record.user_id)

    return user, record


def _assert_identifiers_available(
    session: Session,
    record: UserSubscription,
    *,
    customer_id: str | None,
    subscription_id: str | None,
) -> None:
    clauses = []
    if customer_id:
        clauses.append(
            UserSubscription.provider_customer_id
            == customer_id
        )
    if subscription_id:
        clauses.append(
            UserSubscription.provider_subscription_id
            == subscription_id
        )

    if not clauses:
        return

    conflict = session.scalar(
        select(UserSubscription).where(
            or_(*clauses),
            UserSubscription.id != record.id,
        )
    )

    if conflict is not None:
        raise BillingWebhookConflictError(
            "Stripe identifiers are already connected "
            "to another BXK account."
        )


def _subscription_price_id(obj: Any) -> str | None:
    metadata_price = str(
        _metadata(obj).get(
            "provider_price_id",
            "",
        )
        or ""
    ).strip()
    if metadata_price:
        return metadata_price

    items = _value(obj, "items", {})
    data = _value(items, "data", []) or []

    for item in data:
        price = _value(item, "price", {})
        price_id = str(
            _value(price, "id", "") or ""
        ).strip()
        if price_id:
            return price_id

    return None


def _subscription_period_end(obj: Any) -> datetime | None:
    direct = _timestamp(
        _value(obj, "current_period_end")
    )
    if direct is not None:
        return direct

    items = _value(obj, "items", {})
    data = _value(items, "data", []) or []
    item_ends = [
        timestamp
        for timestamp in (
            _timestamp(
                _value(item, "current_period_end")
            )
            for item in data
        )
        if timestamp is not None
    ]
    return max(item_ends) if item_ends else None


def _is_stale(
    record: UserSubscription,
    event_created_at: datetime | None,
) -> bool:
    previous = _normalize_datetime(
        record.provider_event_created_at
    )
    incoming = _normalize_datetime(
        event_created_at
    )
    return bool(
        previous is not None
        and incoming is not None
        and incoming < previous
    )


def _upsert_checkout_completed(
    session: Session,
    obj: Any,
) -> str:
    metadata = _metadata(obj)
    user_id = (
        _value(obj, "client_reference_id")
        or metadata.get("bxk_user_id")
    )
    customer_id = str(
        _value(obj, "customer", "") or ""
    ).strip() or None
    subscription_id = str(
        _value(obj, "subscription", "") or ""
    ).strip() or None

    user, record = _find_subscription_record(
        session,
        user_id=user_id,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )

    if user is None:
        raise BillingWebhookError(
            "Checkout Session does not identify a BXK "
            "user."
        )

    if record is None:
        record = UserSubscription(
            user_id=user.id,
            provider=SubscriptionProvider.STRIPE,
            plan_code=SubscriptionPlan.PRO,
            status=SubscriptionStatus.INCOMPLETE,
        )
        session.add(record)
        session.flush()

    _assert_identifiers_available(
        session,
        record,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )

    record.provider = SubscriptionProvider.STRIPE
    record.provider_customer_id = (
        customer_id or record.provider_customer_id
    )
    record.provider_subscription_id = (
        subscription_id
        or record.provider_subscription_id
    )

    metadata_price = str(
        metadata.get("provider_price_id", "")
        or ""
    ).strip()
    if metadata_price:
        record.provider_price_id = metadata_price

    return "CHECKOUT_LINKED"


def _upsert_subscription_event(
    session: Session,
    *,
    event_id: str,
    event_created_at: datetime | None,
    obj: Any,
) -> str:
    metadata = _metadata(obj)
    subscription_id = str(
        _value(obj, "id", "") or ""
    ).strip() or None
    customer_id = str(
        _value(obj, "customer", "") or ""
    ).strip() or None

    user, record = _find_subscription_record(
        session,
        user_id=metadata.get("bxk_user_id"),
        customer_id=customer_id,
        subscription_id=subscription_id,
    )

    if user is None:
        return "IGNORED_UNMATCHED_SUBSCRIPTION"

    if record is None:
        record = UserSubscription(
            user_id=user.id,
            provider=SubscriptionProvider.STRIPE,
            plan_code=SubscriptionPlan.PRO,
            status=SubscriptionStatus.INCOMPLETE,
        )
        session.add(record)
        session.flush()

    if _is_stale(record, event_created_at):
        return "IGNORED_STALE_EVENT"

    _assert_identifiers_available(
        session,
        record,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )

    raw_status = str(
        _value(obj, "status", "") or ""
    ).strip().lower()
    mapped_status = STRIPE_STATUS_MAP.get(
        raw_status
    )

    if mapped_status is None:
        raise BillingWebhookError(
            "Stripe subscription status is unsupported."
        )

    prior_status = record.status
    record.provider = SubscriptionProvider.STRIPE
    record.provider_customer_id = (
        customer_id or record.provider_customer_id
    )
    record.provider_subscription_id = (
        subscription_id
        or record.provider_subscription_id
    )
    record.provider_price_id = (
        _subscription_price_id(obj)
        or record.provider_price_id
    )
    record.plan_code = SubscriptionPlan.PRO
    record.status = mapped_status
    record.current_period_end = (
        _subscription_period_end(obj)
    )
    record.trial_ends_at = _timestamp(
        _value(obj, "trial_end")
    )
    record.cancel_at_period_end = bool(
        _value(obj, "cancel_at_period_end", False)
    )

    if mapped_status == SubscriptionStatus.PAST_DUE:
        if (
            prior_status != SubscriptionStatus.PAST_DUE
            or record.grace_period_ends_at is None
        ):
            record.grace_period_ends_at = (
                datetime.now(timezone.utc)
                + timedelta(
                    days=int(
                        config
                        .BXK_STRIPE_PAST_DUE_GRACE_DAYS
                    )
                )
            )
    else:
        record.grace_period_ends_at = None

    record.provider_event_created_at = (
        event_created_at
    )
    record.provider_event_id = event_id

    return "SUBSCRIPTION_SYNCHRONIZED"


def _invoice_subscription_id(obj: Any) -> str | None:
    legacy = str(
        _value(obj, "subscription", "") or ""
    ).strip()
    if legacy:
        return legacy

    parent = _value(obj, "parent", {})
    details = _value(
        parent,
        "subscription_details",
        {},
    )
    current = str(
        _value(details, "subscription", "")
        or ""
    ).strip()
    return current or None


def _process_invoice_event(
    session: Session,
    *,
    event_type: str,
    event_id: str,
    event_created_at: datetime | None,
    obj: Any,
) -> str:
    subscription_id = _invoice_subscription_id(
        obj
    )
    if not subscription_id:
        return "IGNORED_NON_SUBSCRIPTION_INVOICE"

    record = session.scalar(
        select(UserSubscription).where(
            UserSubscription.provider_subscription_id
            == subscription_id
        )
    )
    if record is None:
        return "IGNORED_UNMATCHED_INVOICE"

    if _is_stale(record, event_created_at):
        return "IGNORED_STALE_EVENT"

    # A failed renewal immediately starts the configured
    # grace window. A paid invoice is recorded but access
    # is changed only by the authoritative subscription
    # status event that Stripe sends alongside it.
    if event_type == "invoice.payment_failed":
        if record.status != SubscriptionStatus.PAST_DUE:
            record.grace_period_ends_at = (
                datetime.now(timezone.utc)
                + timedelta(
                    days=int(
                        config
                        .BXK_STRIPE_PAST_DUE_GRACE_DAYS
                    )
                )
            )
        record.status = SubscriptionStatus.PAST_DUE
        record.provider_event_created_at = (
            event_created_at
        )
        record.provider_event_id = event_id
        return "PAYMENT_FAILURE_RECORDED"

    return "PAYMENT_RECORDED"


def process_stripe_webhook(
    session: Session,
    *,
    event: Any,
    payload: bytes,
) -> dict:
    event_data = _as_dict(event)
    event_id = str(
        event_data.get("id", "") or ""
    ).strip()
    event_type = str(
        event_data.get("type", "") or ""
    ).strip()

    if not event_id or not event_type:
        raise BillingWebhookError(
            "Stripe event ID and type are required."
        )

    digest = hashlib.sha256(payload).hexdigest()
    existing = session.get(
        BillingWebhookEvent,
        event_id,
    )

    if existing is not None:
        if existing.payload_digest != digest:
            raise BillingWebhookConflictError(
                "A Stripe event ID was reused with a "
                "different payload."
            )
        return {
            "processed": False,
            "duplicate": True,
            "outcome": "DUPLICATE_EVENT",
        }

    ledger = BillingWebhookEvent(
        provider_event_id=event_id,
        event_type=event_type,
        payload_digest=digest,
    )
    session.add(ledger)

    data = event_data.get("data")
    obj = (
        data.get("object")
        if isinstance(data, Mapping)
        else None
    )
    if not isinstance(obj, Mapping):
        raise BillingWebhookError(
            "Stripe event data object is required."
        )

    event_created_at = _timestamp(
        event_data.get("created")
    )

    if event_type == "checkout.session.completed":
        outcome = _upsert_checkout_completed(
            session,
            obj,
        )
    elif event_type in SUBSCRIPTION_EVENT_TYPES:
        outcome = _upsert_subscription_event(
            session,
            event_id=event_id,
            event_created_at=event_created_at,
            obj=obj,
        )
    elif event_type in INVOICE_EVENT_TYPES:
        outcome = _process_invoice_event(
            session,
            event_type=event_type,
            event_id=event_id,
            event_created_at=event_created_at,
            obj=obj,
        )
    else:
        outcome = "IGNORED_EVENT_TYPE"

    ledger.processed_at = datetime.now(
        timezone.utc
    )

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        duplicate = session.get(
            BillingWebhookEvent,
            event_id,
        )
        if (
            duplicate is not None
            and duplicate.payload_digest == digest
        ):
            return {
                "processed": False,
                "duplicate": True,
                "outcome": "DUPLICATE_EVENT",
            }
        raise

    return {
        "processed": True,
        "duplicate": False,
        "outcome": outcome,
    }


def billing_status_for_user(
    session: Session,
    user: User,
) -> dict:
    subscription = get_user_subscription(
        session,
        user.id,
    )
    access = evaluate_subscription_access(
        user,
        subscription,
    )
    configuration = billing_configuration_status()

    return {
        "billing": configuration,
        "subscription": access,
        "can_manage_billing": bool(
            subscription
            and subscription.provider
            == SubscriptionProvider.STRIPE
            and subscription.provider_customer_id
        ),
    }
