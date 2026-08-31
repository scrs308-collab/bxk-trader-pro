import os
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from bxk_app.database import (
    database_configured,
    get_session_factory,
)
from bxk_app.db_models.overnight_alert_state import (
    OvernightAlertState,
)
from bxk_app.services.sms_consent_service import (
    has_active_sms_consent,
    normalize_sms_phone,
)
from bxk_app.services.sms_service import (
    send_bxk_sms,
)


EASTERN = ZoneInfo("America/New_York")


def _env(name: str) -> str:
    return str(
        os.getenv(name, "")
    ).strip()


def _enabled(
    name: str,
    default: str = "false",
) -> bool:
    value = str(
        os.getenv(
            name,
            default,
        )
    ).strip().lower()

    return value not in {
        "",
        "0",
        "false",
        "no",
        "off",
    }


def _mask_phone(
    phone: str,
) -> str | None:
    digits = "".join(
        char
        for char in str(phone or "")
        if char.isdigit()
    )

    if len(digits) < 4:
        return None

    return f"***-***-{digits[-4:]}"


def _alert_history():
    result = {
        "last_successful_alert_at": None,
        "last_successful_alert_state": None,
        "last_successful_alert_scope": None,
        "overnight_state": None,
        "daytime_worst_state": None,
    }

    if not database_configured():
        return result

    try:
        factory = get_session_factory()

        with factory() as session:
            rows = session.execute(
                select(
                    OvernightAlertState
                ).where(
                    OvernightAlertState.scope.like(
                        "OWNER_%"
                    )
                )
            ).scalars().all()

    except Exception:
        return result

    rank = {
        None: -1,
        "GREEN": 0,
        "YELLOW": 1,
        "ORANGE": 2,
        "RED": 3,
        "CRITICAL": 4,
    }

    latest = None
    worst_daytime = None

    for row in rows:
        scope = str(
            row.scope or ""
        )

        state = str(
            row.state or ""
        ).strip().upper() or None

        if scope == "OWNER_OVERNIGHT":
            result["overnight_state"] = state

        if scope.startswith(
            "OWNER_DAYTIME:"
        ):
            if (
                worst_daytime is None
                or rank.get(
                    state,
                    -1,
                )
                > rank.get(
                    worst_daytime,
                    -1,
                )
            ):
                worst_daytime = state

        alerted_at = getattr(
            row,
            "last_alerted_at",
            None,
        )

        if alerted_at is not None:
            if (
                latest is None
                or alerted_at
                > latest.last_alerted_at
            ):
                latest = row

    result["daytime_worst_state"] = (
        worst_daytime
    )

    if latest is not None:
        result[
            "last_successful_alert_at"
        ] = latest.last_alerted_at.isoformat()

        result[
            "last_successful_alert_state"
        ] = str(
            latest.last_alerted_state
            or latest.state
            or ""
        ).strip().upper() or None

        scope = str(
            latest.scope or ""
        )

        result[
            "last_successful_alert_scope"
        ] = (
            "DAYTIME"
            if scope.startswith(
                "OWNER_DAYTIME:"
            )
            else "OVERNIGHT"
        )

    return result


def get_sms_diagnostics():
    phone = _env(
        "BXK_ALERT_PHONE"
    )

    config = {
        "account_sid":
            bool(
                _env(
                    "BXK_TWILIO_ACCOUNT_SID"
                )
            ),
        "auth_token":
            bool(
                _env(
                    "BXK_TWILIO_AUTH_TOKEN"
                )
            ),
        "from_number":
            bool(
                _env(
                    "BXK_TWILIO_FROM_NUMBER"
                )
            ),
        "recipient":
            bool(phone),
    }

    transport_configured = all(
        config.values()
    )

    consent_active = False
    consent_error = None

    if (
        phone
        and database_configured()
    ):
        try:
            normalized = (
                normalize_sms_phone(
                    phone
                )
            )

            consent_active = (
                has_active_sms_consent(
                    normalized
                )
            )

        except Exception as exc:
            consent_error = (
                type(exc).__name__
            )

    history = _alert_history()

    alerts_enabled = _enabled(
        "BXK_SMS_ALERTS_ENABLED",
        "false",
    )

    return {
        "alerts_enabled":
            alerts_enabled,
        "transport_configured":
            transport_configured,
        "database_configured":
            database_configured(),
        "consent_active":
            consent_active,
        "consent_error":
            consent_error,
        "recipient_masked":
            _mask_phone(phone),
        "ready":
            (
                alerts_enabled
                and transport_configured
                and database_configured()
                and consent_active
            ),
        **history,
    }


def send_test_sms():
    diagnostics = (
        get_sms_diagnostics()
    )

    if not diagnostics["alerts_enabled"]:
        raise RuntimeError(
            "SMS alerts are disabled."
        )

    if not diagnostics[
        "transport_configured"
    ]:
        raise RuntimeError(
            "SMS transport configuration "
            "is incomplete."
        )

    if not diagnostics[
        "database_configured"
    ]:
        raise RuntimeError(
            "Database is not configured."
        )

    if not diagnostics[
        "consent_active"
    ]:
        raise RuntimeError(
            "SMS recipient does not have "
            "active consent."
        )

    now = datetime.now(
        EASTERN
    )

    stamp = now.strftime(
        "%I:%M %p ET"
    ).lstrip("0")

    message = (
        "BXK TRADER PRO TEST\n"
        "SMS alert path is working.\n"
        f"{stamp}"
    )

    send_bxk_sms(
        message
    )

    return {
        "status": "SENT",
        "sent": True,
        "sent_at":
            now.isoformat(),
        "recipient_masked":
            diagnostics[
                "recipient_masked"
            ],
    }
