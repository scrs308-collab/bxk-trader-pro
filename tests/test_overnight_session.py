from datetime import datetime
from zoneinfo import ZoneInfo

from bxk_app.overnight_session import (
    get_spx_gth_session,
)


ET = ZoneInfo("America/New_York")


def et(year, month, day, hour, minute):
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=ET,
    )


def test_weekday_evening_is_gth():
    result = get_spx_gth_session(
        et(2026, 8, 19, 21, 0)
    )

    assert result["active"] is True
    assert result["state"] == "GTH"


def test_weekday_morning_is_gth():
    result = get_spx_gth_session(
        et(2026, 8, 20, 8, 0)
    )

    assert result["active"] is True


def test_925_is_not_gth():
    result = get_spx_gth_session(
        et(2026, 8, 20, 9, 25)
    )

    assert result["active"] is False


def test_regular_market_time_is_not_gth():
    result = get_spx_gth_session(
        et(2026, 8, 20, 12, 0)
    )

    assert result["active"] is False


def test_saturday_is_not_gth():
    result = get_spx_gth_session(
        et(2026, 8, 22, 8, 0)
    )

    assert result["active"] is False


def test_sunday_evening_is_gth():
    result = get_spx_gth_session(
        et(2026, 8, 23, 21, 0)
    )

    assert result["active"] is True


def test_sunday_morning_is_not_gth():
    result = get_spx_gth_session(
        et(2026, 8, 23, 8, 0)
    )

    assert result["active"] is False


def test_friday_evening_is_not_gth():
    result = get_spx_gth_session(
        et(2026, 8, 21, 21, 0)
    )

    assert result["active"] is False
