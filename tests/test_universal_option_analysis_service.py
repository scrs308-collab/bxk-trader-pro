from bxk_app import (
    universal_option_analysis_service
    as service,
)


def discovery(
    symbol="SPY",
    dtes=(0, 1, 2),
):
    return {
        "symbol": symbol,
        "price": 100.0,
        "analysis_enabled": True,
        "instrument_family":
            "SHARE_SETTLED_OPTION_UNDERLYING",
        "delivery_style": "SHARES",
        "verified_profile": False,
        "exercise_style": "UNKNOWN",
        "early_assignment_risk": None,
        "expirations": [
            {
                "dte": value,
            }
            for value in dtes
        ],
        "reason_code":
            "DISCOVERY_READY",
    }


def expected_ready():
    return {
        "available": True,
        "expected_move": 3.0,
        "expected_move_pct": 3.0,
        "source":
            "OPTION_CHAIN_ATM_STRADDLE",
        "reason_code":
            "OPTION_CHAIN_EXPECTED_MOVE_READY",
    }


def priced_candidate():
    return {
        "available": True,
        "pricing_ready": True,
        "signal_ready": False,
        "execution_enabled": False,
        "observation_only": True,
        "reason_code":
            "CONDOR_CANDIDATE_PRICED",
        "candidate": {
            "underlying": "SPY",
            "buy_put": 92.0,
            "sell_put": 97.0,
            "sell_call": 103.0,
            "buy_call": 108.0,
            "wing_width": 5.0,
            "live_credit": 0.50,
        },
    }


def test_dte_is_required(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "discover_underlying",
        lambda symbol:
            discovery(symbol),
    )

    result = (
        service.analyze_underlying(
            "SPY"
        )
    )

    assert (
        result["reason_code"]
        == "DTE_REQUIRED"
    )

    assert (
        result["execution_enabled"]
        is False
    )


def test_unavailable_dte_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "discover_underlying",
        lambda symbol:
            discovery(
                symbol,
                dtes=(2, 9),
            ),
    )

    result = (
        service.analyze_underlying(
            "DIA",
            days_to_expiration=0,
            wing_width=5,
        )
    )

    assert (
        result["available_dtes"]
        == [2, 9]
    )

    assert (
        result["reason_code"]
        == "DTE_UNAVAILABLE"
    )

    assert (
        result["execution_enabled"]
        is False
    )


def test_expected_move_uses_requested_symbol_and_dte(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "discover_underlying",
        lambda symbol:
            discovery(symbol),
    )

    requested = {}

    def fake_expected(
        symbol,
        price,
        days_to_expiration=0,
    ):
        requested["symbol"] = symbol
        requested["price"] = price
        requested["dte"] = (
            days_to_expiration
        )

        return expected_ready()

    monkeypatch.setattr(
        service,
        "calculate_atm_straddle_expected_move",
        fake_expected,
    )

    monkeypatch.setattr(
        service,
        "build_and_price_underlying_condor",
        lambda *args, **kwargs:
            priced_candidate(),
    )

    result = (
        service.analyze_underlying(
            "SPY",
            days_to_expiration=0,
            wing_width=5,
        )
    )

    assert requested == {
        "symbol": "SPY",
        "price": 100.0,
        "dte": 0,
    }

    assert (
        result[
            "expected_move_available"
        ]
        is True
    )


def test_universal_candidate_can_be_priced(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "discover_underlying",
        lambda symbol:
            discovery(symbol),
    )

    monkeypatch.setattr(
        service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs:
            expected_ready(),
    )

    monkeypatch.setattr(
        service,
        "build_and_price_underlying_condor",
        lambda *args, **kwargs:
            priced_candidate(),
    )

    result = (
        service.analyze_underlying(
            "SPY",
            days_to_expiration=0,
            wing_width=5,
        )
    )

    assert (
        result["analysis_ready"]
        is True
    )

    assert (
        result["candidate_available"]
        is True
    )

    assert (
        result[
            "candidate_pricing_ready"
        ]
        is True
    )

    assert (
        result["execution_enabled"]
        is False
    )


def test_unknown_symbol_without_wing_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "discover_underlying",
        lambda symbol:
            discovery(symbol),
    )

    monkeypatch.setattr(
        service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs:
            expected_ready(),
    )

    monkeypatch.setattr(
        service,
        "build_and_price_underlying_condor",
        lambda *args, **kwargs: {
            "available": False,
            "pricing_ready": False,
            "execution_enabled": False,
            "reason_code":
                "WING_WIDTH_REQUIRED",
            "candidate": None,
        },
    )

    result = (
        service.analyze_underlying(
            "SPY",
            days_to_expiration=0,
        )
    )

    assert (
        result["reason_code"]
        == "WING_WIDTH_REQUIRED"
    )

    assert (
        result["analysis_ready"]
        is False
    )

    assert (
        result["execution_enabled"]
        is False
    )


def test_universal_stability_is_exposed(
    monkeypatch,
):
    base = discovery(
        "SPY",
        dtes=(0,),
    )

    base.update(
        {
            "session_open": 99.0,
            "day_high": 101.0,
            "day_low": 98.0,
            "prev_close": 98.5,
        }
    )

    monkeypatch.setattr(
        service,
        "discover_underlying",
        lambda symbol: base,
    )

    monkeypatch.setattr(
        service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: {
            "available": True,
            "expected_move": 4.0,
            "expected_move_pct": 4.0,
            "source":
                "OPTION_CHAIN_ATM_STRADDLE",
            "reason_code":
                "OPTION_CHAIN_EXPECTED_MOVE_READY",
        },
    )

    monkeypatch.setattr(
        service,
        "get_market_session_phase",
        lambda: {
            "market_status": "LIVE",
            "session_phase": "EARLY",
            "minutes_since_open": 60,
        },
    )

    monkeypatch.setattr(
        service,
        "calculate_range_expansion_pressure",
        lambda **kwargs: {
            "available": True,
            "pressure_ratio": 1.0,
        },
    )

    monkeypatch.setattr(
        service,
        "calculate_condor_stability_score",
        lambda **kwargs: {
            "available": True,
            "score": 80.0,
        },
    )

    monkeypatch.setattr(
        service,
        "build_and_price_underlying_condor",
        lambda *args, **kwargs:
            priced_candidate(),
    )

    result = (
        service.analyze_underlying(
            "SPY",
            days_to_expiration=0,
            wing_width=5,
        )
    )

    assert (
        result["stability_available"]
        is True
    )

    assert (
        result["stability_signal_ready"]
        is True
    )

    assert (
        result["stability_score"]
        == 80.0
    )

    assert (
        result["execution_enabled"]
        is False
    )


def test_universal_decision_is_exposed(
    monkeypatch,
):
    base = discovery(
        "SPY",
        dtes=(0,),
    )

    base.update(
        {
            "session_open": 99.0,
            "day_high": 101.0,
            "day_low": 98.0,
            "prev_close": 98.5,
            "verified_profile": False,
        }
    )

    monkeypatch.setattr(
        service,
        "discover_underlying",
        lambda symbol: base,
    )

    monkeypatch.setattr(
        service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: {
            "available": True,
            "expected_move": 4.0,
            "expected_move_pct": 4.0,
            "source":
                "OPTION_CHAIN_ATM_STRADDLE",
        },
    )

    monkeypatch.setattr(
        service,
        "get_market_session_phase",
        lambda: {
            "market_status": "LIVE",
            "session_phase": "EARLY",
            "minutes_since_open": 60,
        },
    )

    monkeypatch.setattr(
        service,
        "calculate_range_expansion_pressure",
        lambda **kwargs: {
            "available": True,
            "pressure_ratio": 1.0,
        },
    )

    monkeypatch.setattr(
        service,
        "calculate_condor_stability_score",
        lambda **kwargs: {
            "available": True,
            "score": 82.0,
        },
    )

    monkeypatch.setattr(
        service,
        "build_and_price_underlying_condor",
        lambda *args, **kwargs:
            priced_candidate(),
    )

    result = (
        service.analyze_underlying(
            "SPY",
            days_to_expiration=0,
            wing_width=5,
        )
    )

    assert (
        result["strategy_status"]
        == "APPROVED"
    )

    assert (
        result["market_permission"]
        == "TRADE"
    )

    assert (
        result["final_decision"]
        == "NO TRADE"
    )

    assert (
        result["decision_reason_code"]
        == (
            "UNVERIFIED_PROFILE_"
            "EXECUTION_BLOCKED"
        )
    )

    assert (
        result["execution_enabled"]
        is False
    )
