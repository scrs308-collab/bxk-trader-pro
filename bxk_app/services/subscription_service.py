from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.db_models.subscription import (
    SubscriptionPlan,
    SubscriptionProvider,
    SubscriptionStatus,
    UserSubscription,
)
from bxk_app.db_models.user import User, UserRole


ACCESSIBLE_STATUSES = {
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.TRIALING,
}


def _enum_value(value) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        return value

    return str(value.value)


def _isoformat(value) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _is_future(
    value,
    now: datetime,
) -> bool:
    if value is None:
        return False

    comparison_value = value
    comparison_now = now

    if comparison_value.tzinfo is None:
        comparison_value = (
            comparison_value.replace(
                tzinfo=timezone.utc
            )
        )

    if comparison_now.tzinfo is None:
        comparison_now = comparison_now.replace(
            tzinfo=timezone.utc
        )

    return comparison_value > comparison_now


def get_user_subscription(
    session: Session,
    user_id,
) -> UserSubscription | None:
    return session.scalar(
        select(UserSubscription).where(
            UserSubscription.user_id
            == user_id
        )
    )


def evaluate_subscription_access(
    user: User,
    subscription: UserSubscription | None,
    *,
    enforcement_enabled: bool | None = None,
    now: datetime | None = None,
) -> dict:
    if enforcement_enabled is None:
        enforcement_enabled = bool(
            config
            .BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED
        )

    current_time = now or datetime.now(
        timezone.utc
    )

    role = _enum_value(user.role)

    if role == UserRole.OWNER.value:
        granted = True
        reason = "OWNER_BYPASS"
    elif enforcement_enabled is False:
        granted = True
        reason = "ENFORCEMENT_DISABLED"
    elif subscription is None:
        granted = False
        reason = "NO_SUBSCRIPTION"
    elif subscription.manual_access_granted is False:
        granted = False
        reason = "MANUAL_DENY"
    elif (
        subscription.manual_access_granted is True
        and (
            subscription.manual_access_expires_at
            is None
            or _is_future(
                subscription
                .manual_access_expires_at,
                current_time,
            )
        )
    ):
        granted = True
        reason = "MANUAL_ACCESS"
    elif (
        subscription.status
        in ACCESSIBLE_STATUSES
    ):
        granted = True
        reason = (
            "ACTIVE_SUBSCRIPTION"
            if subscription.status
            == SubscriptionStatus.ACTIVE
            else "ACTIVE_TRIAL"
        )
    elif (
        subscription.status
        == SubscriptionStatus.PAST_DUE
        and _is_future(
            subscription.grace_period_ends_at,
            current_time,
        )
    ):
        granted = True
        reason = "PAYMENT_GRACE_PERIOD"
    else:
        granted = False
        reason = "SUBSCRIPTION_INACTIVE"

    return {
        "enforcement_enabled": bool(
            enforcement_enabled
        ),
        "access_granted": granted,
        "access_reason": reason,
        "plan": (
            _enum_value(subscription.plan_code)
            if subscription
            else None
        ),
        "status": (
            _enum_value(subscription.status)
            if subscription
            else None
        ),
        "provider": (
            _enum_value(subscription.provider)
            if subscription
            else None
        ),
        "current_period_end": (
            _isoformat(
                subscription.current_period_end
            )
            if subscription
            else None
        ),
        "trial_ends_at": (
            _isoformat(
                subscription.trial_ends_at
            )
            if subscription
            else None
        ),
        "grace_period_ends_at": (
            _isoformat(
                subscription
                .grace_period_ends_at
            )
            if subscription
            else None
        ),
        "cancel_at_period_end": bool(
            subscription
            and subscription
            .cancel_at_period_end
        ),
        "manual_access_granted": (
            subscription.manual_access_granted
            if subscription
            else None
        ),
        "manual_access_expires_at": (
            _isoformat(
                subscription
                .manual_access_expires_at
            )
            if subscription
            else None
        ),
    }


def get_subscription_access(
    session: Session,
    user: User,
    *,
    enforcement_enabled: bool | None = None,
    now: datetime | None = None,
) -> dict:
    if enforcement_enabled is None:
        enforcement_enabled = bool(
            config
            .BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED
        )

    subscription = get_user_subscription(
        session,
        user.id,
    )

    return evaluate_subscription_access(
        user,
        subscription,
        enforcement_enabled=(
            enforcement_enabled
        ),
        now=now,
    )


def set_manual_subscription_access(
    session: Session,
    *,
    user_id: str,
    granted: bool | None,
    expires_at: datetime | None = None,
) -> dict:
    try:
        parsed_user_id = uuid.UUID(
            str(user_id or "")
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "Invalid user ID."
        ) from exc

    user = session.get(
        User,
        parsed_user_id,
    )

    if user is None:
        raise LookupError(
            "User not found."
        )

    role = _enum_value(user.role)

    if role == UserRole.OWNER.value:
        raise ValueError(
            "OWNER accounts do not require "
            "subscription access overrides."
        )

    if granted is not True and expires_at:
        raise ValueError(
            "An expiration date requires "
            "granted access."
        )

    subscription = get_user_subscription(
        session,
        user.id,
    )

    if subscription is None:
        subscription = UserSubscription(
            user_id=user.id,
            provider=(
                SubscriptionProvider.MANUAL
            ),
            plan_code=SubscriptionPlan.PRO,
            status=(
                SubscriptionStatus.INCOMPLETE
            ),
        )
        session.add(subscription)

    subscription.manual_access_granted = (
        granted
    )
    subscription.manual_access_expires_at = (
        expires_at
        if granted is True
        else None
    )

    session.commit()
    session.refresh(subscription)

    return evaluate_subscription_access(
        user,
        subscription,
        enforcement_enabled=bool(
            config
            .BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED
        ),
    )
