from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import uuid

from sqlalchemy import select

from bxk_app.database import get_session_factory
from bxk_app.db_models.sms_alert_delivery import SmsAlertDelivery
from bxk_app.db_models.user import User, UserRole


EASTERN = ZoneInfo("America/New_York")

AFTER_HOURS = "AFTER_HOURS"
AFTER_HOURS_CRITICAL = "AFTER_HOURS_CRITICAL"
ALL = "ALL"
OFF = "OFF"

VALID_MODES = {
    AFTER_HOURS,
    AFTER_HOURS_CRITICAL,
    ALL,
    OFF,
}

DEFAULT_MODE = AFTER_HOURS
DAYTIME_ALERT_LIMIT = 3
DAYTIME_WINDOW_MINUTES = 60


def normalize_mode(value):
    mode = str(value or DEFAULT_MODE).strip().upper()
    if mode not in VALID_MODES:
        raise ValueError("Invalid SMS alert mode.")
    return mode


def _user_id(value):
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid user ID.") from exc


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_preferences(user_id, *, session_factory=None):
    factory = session_factory or get_session_factory()
    parsed = _user_id(user_id)
    now = datetime.now(timezone.utc)

    with factory() as session:
        user = session.get(User, parsed)
        if user is None:
            raise LookupError("User not found.")

        snoozed_until = _as_utc(user.sms_snoozed_until)
        mode = normalize_mode(user.sms_alert_mode)

        return {
            "alert_mode": mode,
            "snoozed_until": (
                snoozed_until.isoformat()
                if snoozed_until
                else None
            ),
            "snoozed": bool(
                snoozed_until
                and snoozed_until > now
            ),
            "daytime_enabled": mode in {
                AFTER_HOURS_CRITICAL,
                ALL,
            },
            "overnight_enabled": mode != OFF,
        }


def set_mode(user_id, mode, *, session_factory=None):
    factory = session_factory or get_session_factory()
    parsed = _user_id(user_id)
    normalized = normalize_mode(mode)

    with factory() as session:
        user = session.get(User, parsed)
        if user is None:
            raise LookupError("User not found.")
        user.sms_alert_mode = normalized
        session.commit()

    return get_preferences(parsed, session_factory=factory)


def set_snooze(user_id, action, *, session_factory=None):
    factory = session_factory or get_session_factory()
    parsed = _user_id(user_id)
    now = datetime.now(timezone.utc)
    action = str(action or "").strip().upper()

    if action == "ONE_HOUR":
        until = now + timedelta(hours=1)
    elif action == "UNTIL_TOMORROW":
        local = now.astimezone(EASTERN)
        tomorrow = local.date() + timedelta(days=1)
        until = datetime(
            tomorrow.year,
            tomorrow.month,
            tomorrow.day,
            8,
            0,
            tzinfo=EASTERN,
        ).astimezone(timezone.utc)
    elif action == "RESUME":
        until = None
    else:
        raise ValueError("Invalid SMS snooze action.")

    with factory() as session:
        user = session.get(User, parsed)
        if user is None:
            raise LookupError("User not found.")
        user.sms_snoozed_until = until
        session.commit()

    return get_preferences(parsed, session_factory=factory)


def allows_daytime(mode, state):
    mode = normalize_mode(mode)
    state = str(state or "").strip().upper()
    if mode == AFTER_HOURS_CRITICAL:
        return state == "CRITICAL"
    return mode == ALL


def allows_overnight(mode):
    return normalize_mode(mode) != OFF


def _recent_daytime_deliveries(
    session,
    user_id,
    *,
    now,
):
    cutoff = now - timedelta(
        minutes=DAYTIME_WINDOW_MINUTES
    )

    statement = (
        select(SmsAlertDelivery)
        .where(
            SmsAlertDelivery.user_id == user_id,
            SmsAlertDelivery.kind == "DAYTIME",
            SmsAlertDelivery.sent_at >= cutoff,
        )
        .order_by(
            SmsAlertDelivery.sent_at.asc()
        )
    )

    return list(
        session.scalars(statement).all()
    )


def daytime_delivery_decision(
    user_id,
    state,
    *,
    session_factory=None,
):
    factory = session_factory or get_session_factory()
    parsed = _user_id(user_id)
    now = datetime.now(timezone.utc)
    state = str(state or "").strip().upper()

    with factory() as session:
        user = session.get(User, parsed)

        if user is None:
            return {
                "allowed": False,
                "reason": "NO_USER",
            }

        mode = normalize_mode(
            user.sms_alert_mode
        )

        if not allows_daytime(mode, state):
            return {
                "allowed": False,
                "reason": "MODE",
            }

        snoozed_until = _as_utc(
            user.sms_snoozed_until
        )

        deliveries = _recent_daytime_deliveries(
            session,
            user.id,
            now=now,
        )

        critical_recent = any(
            str(
                delivery.state or ""
            ).upper() == "CRITICAL"
            for delivery in deliveries
        )

        if (
            snoozed_until
            and snoozed_until > now
        ):
            if (
                state == "CRITICAL"
                and not critical_recent
            ):
                return {
                    "allowed": True,
                    "reason":
                        "CRITICAL_BREAKTHROUGH",
                }

            return {
                "allowed": False,
                "reason": "SNOOZED",
            }

        if (
            len(deliveries)
            < DAYTIME_ALERT_LIMIT
        ):
            return {
                "allowed": True,
                "reason": "AVAILABLE",
            }

        if (
            state == "CRITICAL"
            and not critical_recent
        ):
            return {
                "allowed": True,
                "reason":
                    "CRITICAL_BREAKTHROUGH",
            }

        return {
            "allowed": False,
            "reason": "RATE_LIMITED",
        }


def record_delivery(
    user_id,
    kind,
    state,
    *,
    session_factory=None,
):
    factory = session_factory or get_session_factory()
    parsed = _user_id(user_id)

    with factory() as session:
        session.add(
            SmsAlertDelivery(
                user_id=parsed,
                kind=str(
                    kind or ""
                ).strip().upper(),
                state=str(
                    state or ""
                ).strip().upper()
                or None,
                sent_at=datetime.now(
                    timezone.utc
                ),
            )
        )
        session.commit()


def overnight_delivery_allowed(
    user_id,
    *,
    session_factory=None,
):
    preferences = get_preferences(
        user_id,
        session_factory=session_factory,
    )

    if preferences["snoozed"]:
        return False

    return allows_overnight(
        preferences["alert_mode"]
    )



def get_owner_preferences(
    *,
    session_factory=None,
):
    factory = session_factory or get_session_factory()

    with factory() as session:
        owner = session.scalar(
            select(User).where(
                User.role == UserRole.OWNER,
                User.is_active.is_(True),
            )
        )

        if owner is None:
            return {
                "user_id": None,
                "alert_mode": DEFAULT_MODE,
                "snoozed": False,
                "snoozed_until": None,
                "daytime_enabled": False,
                "overnight_enabled": True,
            }

        result = get_preferences(
            owner.id,
            session_factory=factory,
        )

        return {
            "user_id": str(owner.id),
            **result,
        }
