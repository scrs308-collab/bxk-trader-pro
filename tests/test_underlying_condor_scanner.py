from bxk_app import (
    underlying_condor_scanner as scanner,
)


def _strike(
    value,
):
    strike = float(value)

    return {
        "underlying": "QQQ",
        "strike": strike,
        "call": f"QQQ CALL {strike}",
        "put": f"QQQ PUT {strike}",
        "call_streamer": (
            f".QQQCALL{strike}"
        ),
        "put_streamer": (
            f".QQQPUT{strike}"
        ),
        "expiration_date": (
            "2026-08-19"
        ),
        "days_to_expiration": 0,
        "settlement_type": "PM",
    }


def _qqq_strikes():
    return [
        _strike(value)
        for value in range(
            700,
            731,
        )
    ]


def test_qqq_candidate_uses_default_five_point_wings(
    monkeypatch,
):
    monkeypatch.setattr(
        scanner,
        "get_strikes_by_dte",
        lambda symbol, dte: (
            _qqq_strikes()
        ),
    )

    result = (
        scanner
        .build_underlying_iron_condor(
            "QQQ",
            715.74,
            4.21,
            days_to_expiration=0,
        )
    )

    assert result["available"] is True

    trade = result["candidate"]

    assert trade["underlying"] == "QQQ"

    assert trade["sell_put"] == 712.0
    assert trade["buy_put"] == 707.0

    assert trade["sell_call"] == 720.0
    assert trade["buy_call"] == 725.0

    assert trade["wing_width"] == 5.0
    assert trade["put_wing_width"] == 5.0
    assert trade["call_wing_width"] == 5.0

    assert result["signal_ready"] is False
    assert (
        result["execution_enabled"]
        is False
    )
    assert result["observation_only"] is True


def test_exact_wing_is_required(
    monkeypatch,
):
    strikes = [
        item
        for item in _qqq_strikes()
        if item["strike"] != 707.0
    ]

    monkeypatch.setattr(
        scanner,
        "get_strikes_by_dte",
        lambda symbol, dte: strikes,
    )

    result = (
        scanner
        .build_underlying_iron_condor(
            "QQQ",
            715.74,
            4.21,
            wing_width=5,
            days_to_expiration=0,
        )
    )

    assert result["available"] is False

    assert (
        result["reason_code"]
        == "EXACT_WING_STRIKES_UNAVAILABLE"
    )


def test_short_strikes_must_bracket_spot(
    monkeypatch,
):
    monkeypatch.setattr(
        scanner,
        "get_strikes_by_dte",
        lambda symbol, dte: (
            _qqq_strikes()
        ),
    )

    result = (
        scanner
        .build_underlying_iron_condor(
            "QQQ",
            720.0,
            0.10,
            days_to_expiration=0,
        )
    )

    assert result["available"] is False

    assert (
        result["reason_code"]
        == "SHORT_STRIKE_ORDER_INVALID"
    )


def test_candidate_live_pricing(
    monkeypatch,
):
    monkeypatch.setattr(
        scanner,
        "get_strikes_by_dte",
        lambda symbol, dte: (
            _qqq_strikes()
        ),
    )

    monkeypatch.setattr(
        scanner,
        "calculate_iron_condor_credit",
        lambda trade: {
            "live_credit": 1.25,
            "put_credit": 0.65,
            "call_credit": 0.60,
        },
    )

    result = (
        scanner
        .build_and_price_underlying_condor(
            "QQQ",
            715.74,
            4.21,
            days_to_expiration=0,
        )
    )

    assert result["available"] is True
    assert result["pricing_ready"] is True

    trade = result["candidate"]

    assert trade["live_credit"] == 1.25
    assert trade["max_profit"] == 125.0
    assert trade["max_risk"] == 375.0

    assert round(
        trade["return_on_risk"],
        2,
    ) == 33.33

    assert result["signal_ready"] is False
    assert (
        result["execution_enabled"]
        is False
    )

    assert (
        result["reason_code"]
        == "CONDOR_CANDIDATE_PRICED"
    )


def test_invalid_credit_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        scanner,
        "get_strikes_by_dte",
        lambda symbol, dte: (
            _qqq_strikes()
        ),
    )

    monkeypatch.setattr(
        scanner,
        "calculate_iron_condor_credit",
        lambda trade: {
            "live_credit": 0,
        },
    )

    result = (
        scanner
        .build_and_price_underlying_condor(
            "QQQ",
            715.74,
            4.21,
        )
    )

    assert result["available"] is True
    assert result["pricing_ready"] is False

    assert (
        result["reason_code"]
        == "CONDOR_CREDIT_UNAVAILABLE"
    )

    assert (
        result["execution_enabled"]
        is False
    )
