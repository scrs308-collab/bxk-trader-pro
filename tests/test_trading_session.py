from datetime import datetime

from bxk_app.trading_session import (
    MARKET_TIMEZONE,
    get_spx_execution_policy,
    get_spx_session,
)


def market_dt(
    year,
    month,
    day,
    hour,
    minute,
):
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=MARKET_TIMEZONE,
    )


def test_gth_morning():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 8, 0
            )
        )
        == "GTH"
    )


def test_gth_ends_at_925():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 9, 24
            )
        )
        == "GTH"
    )

    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 9, 25
            )
        )
        == "CLOSED"
    )


def test_rth_starts_at_930():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 9, 30
            )
        )
        == "RTH"
    )


def test_rth_runs_to_415():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 16, 14
            )
        )
        == "RTH"
    )

    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 16, 15
            )
        )
        == "CURB"
    )


def test_curb_runs_to_500():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 16, 59
            )
        )
        == "CURB"
    )

    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 17, 0
            )
        )
        == "CLOSED"
    )


def test_evening_gth_starts_at_815():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 20, 14
            )
        )
        == "CLOSED"
    )

    assert (
        get_spx_session(
            market_dt(
                2026, 8, 12, 20, 15
            )
        )
        == "GTH"
    )


def test_friday_evening_is_closed():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 14, 20, 15
            )
        )
        == "CLOSED"
    )


def test_saturday_is_closed():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 15, 12, 0
            )
        )
        == "CLOSED"
    )


def test_sunday_evening_opens_gth():
    assert (
        get_spx_session(
            market_dt(
                2026, 8, 16, 20, 15
            )
        )
        == "GTH"
    )


def test_existing_day_order_only_allowed_rth():
    rth = get_spx_execution_policy(
        market_dt(
            2026, 8, 12, 10, 0
        )
    )

    gth = get_spx_execution_policy(
        market_dt(
            2026, 8, 12, 22, 0
        )
    )

    curb = get_spx_execution_policy(
        market_dt(
            2026, 8, 12, 16, 30
        )
    )

    assert rth["day_order_allowed"] is True
    assert rth[
        "extended_order_required"
    ] is False

    assert gth["day_order_allowed"] is False
    assert gth[
        "extended_order_required"
    ] is True

    assert curb["day_order_allowed"] is False
    assert curb[
        "extended_order_required"
    ] is True
