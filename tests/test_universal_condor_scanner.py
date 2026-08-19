from bxk_app import (
    underlying_condor_scanner as scanner,
)


def make_strikes(
    start=90,
    stop=111,
):
    items = []

    for strike in range(
        start,
        stop,
    ):
        items.append(
            {
                "strike": float(strike),
                "expiration_date":
                    "2026-08-19",
                "days_to_expiration": 0,
                "settlement_type": "PM",

                "call":
                    f"CALL{strike}",
                "put":
                    f"PUT{strike}",

                "call_streamer":
                    f".CALL{strike}",
                "put_streamer":
                    f".PUT{strike}",
            }
        )

    return items


def test_unknown_underlying_can_build_with_explicit_wing(
    monkeypatch,
):
    requested = {}

    def fake_chain(symbol, dte):
        requested["symbol"] = symbol
        requested["dte"] = dte

        return make_strikes()

    monkeypatch.setattr(
        scanner,
        "get_strikes_by_dte",
        fake_chain,
    )

    result = (
        scanner.build_underlying_iron_condor(
            "SPY",
            100.0,
            3.0,
            wing_width=5,
            days_to_expiration=0,
        )
    )

    assert result["available"] is True
    assert result["execution_enabled"] is False

    candidate = result["candidate"]

    assert candidate["underlying"] == "SPY"

    assert (
        candidate["verified_profile"]
        is False
    )

    assert (
        candidate["option_chain_symbol"]
        == "SPY"
    )

    assert candidate["wing_width"] == 5.0

    assert requested == {
        "symbol": "SPY",
        "dte": 0,
    }


def test_unknown_underlying_requires_wing_width(
    monkeypatch,
):
    called = False

    def fake_chain(*args, **kwargs):
        nonlocal called
        called = True
        return make_strikes()

    monkeypatch.setattr(
        scanner,
        "get_strikes_by_dte",
        fake_chain,
    )

    result = (
        scanner.build_underlying_iron_condor(
            "SPY",
            100.0,
            3.0,
            days_to_expiration=0,
        )
    )

    assert result["available"] is False

    assert (
        result["reason_code"]
        == "WING_WIDTH_REQUIRED"
    )

    assert result["execution_enabled"] is False

    # Fail before making an unnecessary chain request.
    assert called is False


def test_verified_qqq_keeps_default_wing(
    monkeypatch,
):
    monkeypatch.setattr(
        scanner,
        "get_strikes_by_dte",
        lambda symbol, dte:
            make_strikes(),
    )

    result = (
        scanner.build_underlying_iron_condor(
            "QQQ",
            100.0,
            3.0,
            days_to_expiration=0,
        )
    )

    assert result["available"] is True

    candidate = result["candidate"]

    assert (
        candidate["verified_profile"]
        is True
    )

    assert candidate["wing_width"] == 5.0

    assert (
        candidate["option_chain_symbol"]
        == "QQQ"
    )


def test_blank_symbol_fails_closed():
    result = (
        scanner.build_underlying_iron_condor(
            "",
            100.0,
            3.0,
            wing_width=5,
        )
    )

    assert result["available"] is False

    assert (
        result["reason_code"]
        == "UNDERLYING_SYMBOL_REQUIRED"
    )

    assert result["execution_enabled"] is False
