import asyncio
import hashlib
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
from bxk_app.services.position_service import (
    get_position_monitor,
)
from bxk_app.services.sms_service import (
    send_bxk_sms,
)
from bxk_app.trading_session import (
    get_spx_session,
)


logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")

ALERT_SCOPE_PREFIX = "OWNER_DAYTIME"
DEFAULT_INTERVAL_SECONDS = 60

STATE_RANK = {
    "GREEN": 0,
    "ORANGE": 1,
    "RED": 2,
    "CRITICAL": 3,
}

ALERT_STATES = {
    "ORANGE",
    "RED",
    "CRITICAL",
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


def daytime_sms_enabled() -> bool:
    return _enabled_value(
        "BXK_SMS_ALERTS_ENABLED",
        "false",
    )


def _monitor_allowed() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False

    return (
        daytime_sms_enabled()
        and database_configured()
    )


def _interval_seconds() -> int:
    raw = os.getenv(
        "BXK_DAYTIME_ALERT_SECONDS",
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


def _number(value):
    try:
        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def _format_number(value):
    number = _number(value)

    if number is None:
        return "N/A"

    if number.is_integer():
        return str(int(number))

    return (
        f"{number:.2f}"
        .rstrip("0")
        .rstrip(".")
    )


def classify_position_threat(
    position: dict,
):
    if not isinstance(position, dict):
        return None

    spx_price = _number(
        position.get("spx_price")
    )

    put_distance = _number(
        position.get("put_distance")
    )

    call_distance = _number(
        position.get("call_distance")
    )

    short_put = _number(
        position.get("sell_put")
    )

    short_call = _number(
        position.get("sell_call")
    )

    if (
        spx_price is None
        or put_distance is None
        or call_distance is None
        or short_put is None
        or short_call is None
    ):
        return None

    if put_distance <= call_distance:
        side = "PUT"
        distance = put_distance
        short_strike = short_put
    else:
        side = "CALL"
        distance = call_distance
        short_strike = short_call

    if distance <= 0:
        state = "CRITICAL"

    elif distance <= 10:
        state = "RED"

    elif distance <= 20:
        state = "ORANGE"

    else:
        state = "GREEN"

    return {
        "state": state,
        "side": side,
        "distance": round(
            distance,
            2,
        ),
        "short_strike": short_strike,
        "spx_price": round(
            spx_price,
            2,
        ),
        "expiration": position.get(
            "expiration"
        ),
        "sell_put": short_put,
        "sell_call": short_call,
    }


def _scope_for_position(
    position: dict,
) -> str:
    signature = "|".join(
        [
            str(
                position.get(
                    "expiration",
                    "",
                )
            ),
            _format_number(
                position.get("sell_put")
            ),
            _format_number(
                position.get("sell_call")
            ),
        ]
    )

    digest = hashlib.sha1(
        signature.encode("utf-8")
    ).hexdigest()[:20]

    return (
        f"{ALERT_SCOPE_PREFIX}:"
        f"{digest}"
    )


def _load_locked_state(
    session,
    scope,
):
    statement = (
        select(
            OvernightAlertState
        )
        .where(
            OvernightAlertState.scope
            == scope
        )
        .with_for_update()
    )

    return session.execute(
        statement
    ).scalar_one_or_none()


def _normalized_state(value):
    state = str(
        value or ""
    ).strip().upper()

    if state not in STATE_RANK:
        return None

    return state


def _should_alert(
    previous_state,
    current_state,
    last_alerted_state,
    previous_side,
    current_side,
):
    current = _normalized_state(
        current_state
    )

    if current not in ALERT_STATES:
        return False

    previous = _normalized_state(
        previous_state
    )

    last_alerted = _normalized_state(
        last_alerted_state
    )

    if (
        previous_side
        and current_side
        and previous_side != current_side
    ):
        return True

    if previous is None:
        return True

    if last_alerted is None:
        return True

    return (
        STATE_RANK[current]
        > STATE_RANK[last_alerted]
    )


def build_daytime_sms(
    risk: dict,
):
    state = risk["state"]
    side = risk["side"]
    distance = risk["distance"]

    headings = {
        "ORANGE":
            "BXK DAYTIME WARNING",
        "RED":
            "BXK DAYTIME DEFEND",
        "CRITICAL":
            "BXK DAYTIME CRITICAL",
    }

    parts = [
        headings.get(
            state,
            "BXK DAYTIME ALERT",
        ),
        (
            f"{side} short: "
            f"{_format_number(risk['short_strike'])}"
        ),
        (
            f"SPX: "
            f"{_format_number(risk['spx_price'])}"
        ),
    ]

    if distance <= 0:
        parts.append(
            "SHORT STRIKE BREACHED: "
            + _format_number(
                abs(distance)
            )
            + " pts"
        )
    else:
        parts.append(
            "Cushion: "
            + _format_number(distance)
            + " pts"
        )

    parts.append(
        "Shorts: "
        + _format_number(
            risk["sell_put"]
        )
        + "P / "
        + _format_number(
            risk["sell_call"]
        )
        + "C"
    )

    if risk.get("expiration"):
        parts.append(
            "Exp: "
            + str(
                risk["expiration"]
            )
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


def process_position_threat(
    position: dict,
    *,
    session_factory=None,
    send_func=send_bxk_sms,
):
    risk = classify_position_threat(
        position
    )

    if risk is None:
        return {
            "action": "DATA_WAIT",
            "alert_sent": False,
        }

    factory = (
        session_factory
        or get_session_factory()
    )

    scope = _scope_for_position(
        position
    )

    current_state = risk["state"]
    current_side = risk["side"]

    with factory() as session:
        stored = _load_locked_state(
            session,
            scope,
        )

        if stored is None:
            stored = OvernightAlertState(
                scope=scope,
                state=None,
                reason_code=None,
            )

            session.add(stored)

        previous_state = (
            _normalized_state(
                stored.state
            )
        )

        previous_side = str(
            stored.reason_code or ""
        ).strip().upper() or None

        if current_state == "GREEN":
            was_alerted = (
                stored.last_alerted_state
                is not None
            )

            stored.state = current_state
            stored.reason_code = (
                current_side
            )

            stored.last_alerted_state = None
            stored.last_alerted_at = None

            session.commit()

            return {
                "action": (
                    "REARMED"
                    if was_alerted
                    else (
                        "BASELINE"
                        if previous_state is None
                        else "UNCHANGED"
                    )
                ),
                "previous_state":
                    previous_state,
                "current_state":
                    current_state,
                "side":
                    current_side,
                "alert_sent": False,
            }

        should_alert = _should_alert(
            previous_state,
            current_state,
            stored.last_alerted_state,
            previous_side,
            current_side,
        )

        if should_alert:
            message = build_daytime_sms(
                risk
            )

            # Send before committing state so a failed
            # SMS remains retryable on the next poll.
            send_func(message)

            stored.last_alerted_state = (
                current_state
            )

            stored.last_alerted_at = (
                datetime.now(
                    EASTERN
                )
            )

        stored.state = current_state
        stored.reason_code = current_side

        session.commit()

        return {
            "action": (
                "ALERTED"
                if should_alert
                else (
                    "UNCHANGED"
                    if previous_state
                    == current_state
                    else "STATE_UPDATED"
                )
            ),
            "previous_state":
                previous_state,
            "current_state":
                current_state,
            "side":
                current_side,
            "distance":
                risk["distance"],
            "alert_sent":
                should_alert,
        }


def run_daytime_alert_check():
    if not _monitor_allowed():
        return {
            "action": "DISABLED",
            "alert_sent": False,
        }

    if get_spx_session() != "RTH":
        return {
            "action": "SESSION_IDLE",
            "alert_sent": False,
        }

    monitor = get_position_monitor()

    if (
        not isinstance(
            monitor,
            dict,
        )
        or monitor.get("status")
        != "OK"
    ):
        return {
            "action": "NO_POSITIONS",
            "alert_sent": False,
        }

    positions = monitor.get(
        "positions"
    ) or []

    results = [
        process_position_threat(
            position
        )
        for position in positions
        if isinstance(
            position,
            dict,
        )
    ]

    alert_count = sum(
        1
        for result in results
        if result.get(
            "alert_sent"
        )
    )

    return {
        "action": (
            "ALERTED"
            if alert_count
            else "CHECKED"
        ),
        "position_count":
            len(positions),
        "alert_count":
            alert_count,
        "alert_sent":
            alert_count > 0,
        "results":
            results,
    }


async def run_daytime_alert_monitor():
    logger.info(
        "BXK daytime short-strike SMS monitor started"
    )

    try:
        while True:
            if _monitor_allowed():
                try:
                    result = (
                        await asyncio.to_thread(
                            run_daytime_alert_check
                        )
                    )

                    if result.get(
                        "alert_sent"
                    ):
                        logger.warning(
                            "BXK daytime short-strike "
                            "SMS alert sent: %s",
                            result.get(
                                "results"
                            ),
                        )

                except Exception:
                    logger.exception(
                        "BXK daytime short-strike "
                        "SMS monitor check failed"
                    )

            await asyncio.sleep(
                _interval_seconds()
            )

    except asyncio.CancelledError:
        raise

    finally:
        logger.info(
            "BXK daytime short-strike "
            "SMS monitor stopped"
        )
