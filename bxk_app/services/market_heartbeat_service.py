import asyncio
import logging
import os
from datetime import datetime
from threading import Lock
from zoneinfo import ZoneInfo

from bxk_app.market_engine import market_engine
from bxk_app.market_session import (
    get_market_session_phase,
)


logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")

DEFAULT_INTERVAL_SECONDS = 15

_status_lock = Lock()

_status = {
    "running": False,
    "active_session": False,
    "last_attempt_at": None,
    "last_success_at": None,
    "last_error": None,
    "consecutive_failures": 0,
}


def _iso_now():
    return datetime.now(EASTERN).isoformat()


def _interval_seconds():
    raw = os.getenv(
        "BXK_MARKET_HEARTBEAT_SECONDS",
        str(DEFAULT_INTERVAL_SECONDS),
    )

    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_INTERVAL_SECONDS

    return max(5, value)


def _heartbeat_allowed():
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False

    raw = os.getenv(
        "BXK_MARKET_HEARTBEAT_ENABLED",
        "true",
    ).strip().lower()

    return raw not in {
        "0",
        "false",
        "no",
        "off",
    }


def _set_status(**values):
    with _status_lock:
        _status.update(values)


def get_market_heartbeat_status():
    with _status_lock:
        result = dict(_status)

    last_success = result.get(
        "last_success_at"
    )

    age_seconds = None

    if last_success:
        try:
            parsed = datetime.fromisoformat(
                last_success
            )

            age_seconds = round(
                (
                    datetime.now(EASTERN)
                    - parsed.astimezone(EASTERN)
                ).total_seconds(),
                1,
            )
        except (
            TypeError,
            ValueError,
        ):
            age_seconds = None

    result["age_seconds"] = age_seconds
    result["interval_seconds"] = (
        _interval_seconds()
    )

    if not _heartbeat_allowed():
        result["healthy"] = True
        result["mode"] = "DISABLED"
    elif not result.get("active_session"):
        result["healthy"] = True
        result["mode"] = "SESSION_IDLE"
    else:
        result["healthy"] = bool(
            result.get("running")
            and last_success
            and age_seconds is not None
            and age_seconds
            <= (_interval_seconds() * 3)
            and result.get(
                "consecutive_failures",
                0,
            ) < 3
        )
        result["mode"] = "ACTIVE"

    return result


async def run_market_heartbeat():
    _set_status(
        running=True,
        last_error=None,
    )

    try:
        while True:
            if not _heartbeat_allowed():
                _set_status(
                    active_session=False,
                )

                await asyncio.sleep(
                    _interval_seconds()
                )

                continue

            session = get_market_session_phase()

            active = (
                session.get(
                    "session_phase"
                )
                != "CLOSED"
            )

            _set_status(
                active_session=active,
            )

            if active:
                attempted_at = _iso_now()

                _set_status(
                    last_attempt_at=attempted_at,
                )

                try:
                    await asyncio.to_thread(
                        market_engine.update
                    )

                    _set_status(
                        last_success_at=_iso_now(),
                        last_error=None,
                        consecutive_failures=0,
                    )

                except Exception as error:
                    with _status_lock:
                        failures = int(
                            _status.get(
                                "consecutive_failures",
                                0,
                            )
                        ) + 1

                    _set_status(
                        last_error=(
                            f"{type(error).__name__}: "
                            f"{error}"
                        ),
                        consecutive_failures=failures,
                    )

                    logger.exception(
                        "Market heartbeat refresh failed"
                    )

            await asyncio.sleep(
                _interval_seconds()
            )

    except asyncio.CancelledError:
        raise

    finally:
        _set_status(
            running=False,
            active_session=False,
        )
