from datetime import datetime

from bxk_app.market_session import (
    get_market_session_phase,
)


def test_opening_phase():
    result = get_market_session_phase(
        datetime(2026, 8, 17, 9, 45)
    )

    assert result["session_phase"] == "OPENING"
    assert result["minutes_since_open"] == 15


def test_early_phase():
    result = get_market_session_phase(
        datetime(2026, 8, 17, 10, 30)
    )

    assert result["session_phase"] == "EARLY"
    assert result["minutes_since_open"] == 60


def test_midday_phase():
    result = get_market_session_phase(
        datetime(2026, 8, 17, 12, 30)
    )

    assert result["session_phase"] == "MIDDAY"
    assert result["minutes_since_open"] == 180


def test_afternoon_phase():
    result = get_market_session_phase(
        datetime(2026, 8, 17, 14, 30)
    )

    assert result["session_phase"] == "AFTERNOON"
    assert result["minutes_since_open"] == 300


def test_late_phase():
    result = get_market_session_phase(
        datetime(2026, 8, 17, 15, 30)
    )

    assert result["session_phase"] == "LATE"
    assert result["minutes_since_open"] == 360


def test_closed_phase():
    result = get_market_session_phase(
        datetime(2026, 8, 16, 12, 0)
    )

    assert result["session_phase"] == "CLOSED"
    assert result["minutes_since_open"] is None
