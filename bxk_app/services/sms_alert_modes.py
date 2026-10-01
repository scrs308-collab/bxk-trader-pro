from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import uuid

from bxk_app.database import get_session_factory
from bxk_app.db_models.user import User


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
