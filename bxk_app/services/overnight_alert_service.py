import asyncio
import logging
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
from bxk_app.services.overnight_risk_service import (
    get_live_overnight_risk,
)
from bxk_app.services.sms_service import (
    send_sms,
)


logger = logging.getLogger(__name__)

EASTERN = ZoneInfo(
    "America/New_York"
)

ALERT_SCOPE = "OWNER_OVERNIGHT"

DEFAULT_INTERVAL_SECONDS = 60

STATE_RANK = {
    "GREEN": 0,
    "YELLOW": 1,
    "ORANGE": 2,
    "RED": 3,
    "CRITICAL": 4,
}


def _enabled_value(
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


def _interval_seconds() -> int:
    raw = os.getenv(
        "BXK_OVERNIGHT_ALERT_SECONDS",
        str(DEFAULT_INTERVAL_SECONDS),
    )

    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_INTERVAL_SECONDS

    return max(
        30,
        value,
    )


def overnight_sms_enabled() -> bool:
    return _enabled_value(
        "BXK_SMS_ALERTS_ENABLED",
        "false",
    )


def _monitor_allowed() -> bool:
    if os.getenv(
        "PYTEST_CURRENT_TEST"
    ):
        return False

    return (
        overnight_sms_enabled()
        and database_configured()
    )


def _normalized_state(value):
    state = str(
        value or ""
    ).strip().upper()

    if state not in STATE_RANK:
        return None

    return state


def _risk_is_alertable(payload):
    if not isinstance(
        payload,
        dict,
    ):
        return False

    if payload.get(
        "available"
    ) is not True:
        return False

    state = _normalized_state(
        payload.get("state")
    )

    if state is None:
        return False

    try:
        position_count = int(
            payload.get(
                "position_count",
                0,
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        position_count = 0

    if position_count < 1:
        return False

    session = (
        payload.get("session")
        if isinstance(
            payload.get("session"),
            dict,
        )
        else {}
    )

    if (
        session.get(
            "overnight_monitoring_active"
        )
        is False
    ):
        return False

    return True


def _should_alert(
    previous_state,
    current_state,
):
    previous = _normalized_state(
        previous_state
    )

    current = _normalized_state(
        current_state
    )

    if (
        previous is None
        or current is None
        or previous == current
    ):
        return False

    if (
        STATE_RANK[current]
        > STATE_RANK[previous]
    ):
        return True

    # Recovery texts are useful, but avoid
    # sending every intermediate de-escalation.
    return (
        current == "GREEN"
        and previous != "GREEN"
    )


def _first_position(payload):
    positions = payload.get(
        "positions"
    )

    if not isinstance(
        positions,
        list,
    ) or not positions:
        return {}, {}

    first = positions[0]

    if not isinstance(first, dict):
        return {}, {}

    position = first.get(
        "position"
    )

    risk = first.get(
        "risk"
    )

    return (
        position
        if isinstance(position, dict)
        else {},
        risk
        if isinstance(risk, dict)
        else {},
    )


def _format_strike(value):
    if value is None:
        return None

    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return str(value)

    if number.is_integer():
        return str(
            int(number)
        )

    return (
        f"{number:.2f}"
        .rstrip("0")
        .rstrip(".")
    )


def build_overnight_sms(
    previous_state,
    current_state,
    payload,
):
    previous = _normalized_state(
        previous_state
    ) or "UNKNOWN"

    current = _normalized_state(
        current_state
    ) or "UNKNOWN"

    recovery = (
        current == "GREEN"
        and previous != "GREEN"
    )

    heading = (
        "BXK OVERNIGHT RECOVERY"
        if recovery
        else "BXK OVERNIGHT ALERT"
    )

    position, risk = (
        _first_position(payload)
    )

    threatened_side = str(
        risk.get(
            "threatened_side",
            "",
        )
        or ""
    ).strip().upper()

    short_put = _format_strike(
        position.get(
            "sell_put"
        )
        or position.get(
            "short_put"
        )
    )

    short_call = _format_strike(
        position.get(
            "sell_call"
        )
        or position.get(
            "short_call"
        )
    )

    recommendation = str(
        payload.get(
            "recommendation",
            "",
        )
        or ""
    ).strip().upper()

    reason_code = str(
        payload.get(
            "reason_code",
            "",
        )
        or ""
    ).strip()

    parts = [
        heading,
        f"{previous} -> {current}",
    ]

    if threatened_side:
        parts.append(
            "Threat: "
            + threatened_side
        )

    if short_put or short_call:
        strikes = []

        if short_put:
            strikes.append(
                f"{short_put}P"
            )

        if short_call:
            strikes.append(
                f"{short_call}C"
            )

        parts.append(
            "Shorts: "
            + " / ".join(strikes)
        )

    if recommendation:
        parts.append(
            "Action: "
            + recommendation
        )

    if reason_code:
        parts.append(
            "Reason: "
            + reason_code
        )

    timestamp = datetime.now(
        EASTERN
    ).strftime(
        "%-I:%M %p ET"
        if os.name != "nt"
        else "%I:%M %p ET"
    ).lstrip("0")

    parts.append(timestamp)

    return "\n".join(parts)


def _load_locked_state(session):
    statement = (
        select(
            OvernightAlertState
        )
        .where(
            OvernightAlertState.scope
            == ALERT_SCOPE
        )
        .with_for_update()
    )

    return session.execute(
        statement
    ).scalar_one_or_none()


def process_overnight_risk(
    payload,
    *,
    session_factory=None,
    send_func=send_sms,
):
    factory = (
        session_factory
        or get_session_factory()
    )

    alertable = (
        _risk_is_alertable(
            payload
        )
    )

    current_state = (
        _normalized_state(
            payload.get("state")
        )
        if alertable
        else None
    )

    reason_code = str(
        payload.get(
            "reason_code",
            "",
        )
        or ""
    ).strip() or None

    with factory() as session:
        state = _load_locked_state(
            session
        )

        if state is None:
            state = OvernightAlertState(
                scope=ALERT_SCOPE,
                state=current_state,
                reason_code=reason_code,
            )

            session.add(state)
            session.commit()

            return {
                "action": (
                    "BASELINE"
                    if current_state
                    else "IDLE"
                ),
                "previous_state": None,
                "current_state":
                    current_state,
                "alert_sent": False,
            }

        previous_state = (
            _normalized_state(
                state.state
            )
        )

        if current_state is None:
            state.state = None
            state.reason_code = (
                reason_code
            )

            session.commit()

            return {
                "action": "IDLE",
                "previous_state":
                    previous_state,
                "current_state": None,
                "alert_sent": False,
            }

        if previous_state is None:
            state.state = (
                current_state
            )

            state.reason_code = (
                reason_code
            )

            session.commit()

            return {
                "action": "BASELINE",
                "previous_state": None,
                "current_state":
                    current_state,
                "alert_sent": False,
            }

        if (
            previous_state
            == current_state
        ):
            state.reason_code = (
                reason_code
            )

            session.commit()

            return {
                "action": "UNCHANGED",
                "previous_state":
                    previous_state,
                "current_state":
                    current_state,
                "alert_sent": False,
            }

        should_alert = (
            _should_alert(
                previous_state,
                current_state,
            )
        )

        if should_alert:
            message = (
                build_overnight_sms(
                    previous_state,
                    current_state,
                    payload,
                )
            )

            # Send before committing the new state.
            # If delivery fails, the transaction
            # remains unchanged and the next poll
            # can retry the alert.
            send_func(message)

            state.last_alerted_state = (
                current_state
            )

            state.last_alerted_at = (
                datetime.now(
                    EASTERN
                )
            )

        state.state = current_state
        state.reason_code = reason_code

        session.commit()

        return {
            "action": (
                "ALERTED"
                if should_alert
                else "STATE_UPDATED"
            ),
            "previous_state":
                previous_state,
            "current_state":
                current_state,
            "alert_sent":
                should_alert,
        }


def run_overnight_alert_check():
    if not _monitor_allowed():
        return {
            "action": "DISABLED",
            "alert_sent": False,
        }

    payload = (
        get_live_overnight_risk()
    )

    return process_overnight_risk(
        payload
    )


async def run_overnight_alert_monitor():
    logger.info(
        "BXK overnight SMS monitor started"
    )

    try:
        while True:
            if _monitor_allowed():
                try:
                    result = (
                        await asyncio.to_thread(
                            run_overnight_alert_check
                        )
                    )

                    if result.get(
                        "alert_sent"
                    ):
                        logger.warning(
                            "BXK overnight SMS "
                            "alert sent: %s -> %s",
                            result.get(
                                "previous_state"
                            ),
                            result.get(
                                "current_state"
                            ),
                        )

                except Exception:
                    logger.exception(
                        "BXK overnight SMS "
                        "monitor check failed"
                    )

            await asyncio.sleep(
                _interval_seconds()
            )

    except asyncio.CancelledError:
        raise

    finally:
        logger.info(
            "BXK overnight SMS monitor stopped"
        )
