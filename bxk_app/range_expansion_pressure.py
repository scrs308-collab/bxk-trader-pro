from math import sqrt


REGULAR_SESSION_MINUTES = 390
MIN_PRESSURE_MINUTES = 5


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def calculate_range_expansion_pressure(
    *,
    directional_consumed_pct,
    minutes_since_open,
    session_phase,
    signal_ready,
):
    """
    Compare actual directional move consumption with the
    square-root-of-time pace expected during a regular session.

    Observation-only.

    This metric does NOT authorize or block trades.
    """

    phase = str(
        session_phase or "UNKNOWN"
    ).upper()

    minutes = _safe_int(
        minutes_since_open
    )

    directional = _safe_float(
        directional_consumed_pct
    )

    if signal_ready is not True:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "reason_code": "SIGNAL_NOT_READY",
            "session_phase": phase,
            "minutes_since_open": minutes,
        }

    if (
        phase == "CLOSED"
        or minutes is None
    ):
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "reason_code": "MARKET_NOT_LIVE",
            "session_phase": phase,
            "minutes_since_open": minutes,
        }

    if directional is None or directional < 0:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "reason_code": "DIRECTIONAL_DATA_UNAVAILABLE",
            "session_phase": phase,
            "minutes_since_open": minutes,
        }

    if minutes < MIN_PRESSURE_MINUTES:
        return {
            "available": False,
            "state": "WARMUP",
            "reason_code": "OPENING_WARMUP",
            "session_phase": phase,
            "minutes_since_open": minutes,
        }

    elapsed = min(
        minutes,
        REGULAR_SESSION_MINUTES,
    )

    expected_pace_pct = (
        sqrt(
            elapsed /
            REGULAR_SESSION_MINUTES
        )
        * 100.0
    )

    pressure_ratio = (
        directional /
        expected_pace_pct
        if expected_pace_pct > 0
        else 0.0
    )

    pace_delta_pct = (
        directional -
        expected_pace_pct
    )

    return {
        "available": True,
        "state": "OBSERVING",
        "reason_code": "PRESSURE_METRICS_AVAILABLE",
        "session_phase": phase,
        "minutes_since_open": minutes,
        "directional_consumed_pct": round(
            directional,
            1,
        ),
        "expected_pace_pct": round(
            expected_pace_pct,
            1,
        ),
        "pressure_ratio": round(
            pressure_ratio,
            2,
        ),
        "pace_delta_pct": round(
            pace_delta_pct,
            1,
        ),
    }
