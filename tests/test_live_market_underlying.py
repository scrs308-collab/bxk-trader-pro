import pytest
from fastapi import HTTPException

from bxk_app.routes import market as market_route
from bxk_app.services import market_service


@pytest.fixture(autouse=True)
def fixed_market_session(monkeypatch):
    monkeypatch.setattr(
        market_service,
        "get_market_session_phase",
        lambda: {
            "session_phase": "EARLY",
            "minutes_since_open": 60,
        },
    )

    monkeypatch.setattr(
        market_service,
        "build_and_price_underlying_condor",
        lambda *args, **kwargs: {
            "available": True,
            "pricing_ready": True,
            "signal_ready": False,
            "execution_enabled": False,
            "observation_only": True,
            "underlying": "QQQ",
            "dte": 0,
            "reason_code": (
                "CONDOR_CANDIDATE_PRICED"
            ),
            "candidate": {
                "underlying": "QQQ",
                "strategy": "IRON CONDOR",
                "sell_put": 712.0,
                "buy_put": 707.0,
                "sell_call": 720.0,
                "buy_call": 725.0,
                "wing_width": 5.0,
                "live_credit": 1.25,
                "max_profit": 125.0,
                "max_risk": 375.0,
                "return_on_risk": 33.33,
            },
        },
    )


def _market_payload():
    return {
        "spx": 7777.25,
        "vix": 14.25,
        "vix1d": 13.90,
        "expected_move": 68.12,
        "market_status": "LIVE",
        "server_time": "2026-08-19T09:30:00",
        "trade_setup": {
            "strategy": "Iron Condor",
        },
        "account": {
            "connected": True,
        },
        "positions": [
            {
                "underlying": "SPX",
                "symbol": "SPXW TEST",
            },
            {
                "underlying": "QQQ",
                "symbol": "QQQ TEST",
            },
        ],
        "qqq": {
            "last": "719.74",
            "open": "720.39",
            "day-high-price": "721.50",
            "day-low-price": "715.50",
            "prev-close": "717.51",
        },
    }


def _expected_move_ready():
    return {
        "available": True,
        "signal_ready": True,
        "underlying": "QQQ",
        "expected_move": 6.70,
        "expected_move_pct": 0.93,
        "atm_strike": 720.0,
        "call_mid": 3.50,
        "put_mid": 3.20,
        "expiration": "2026-08-19",
        "dte": 0,
        "source": "OPTION_CHAIN_ATM_STRADDLE",
        "reason_code": (
            "OPTION_CHAIN_EXPECTED_MOVE_READY"
        ),
    }


def test_live_market_defaults_to_spx(monkeypatch):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    result = market_service.get_live_market()

    assert result["underlying"] == "SPX"
    assert result["price"] == 7777.25
    assert result["execution_enabled"] is True

    assert result["spx"] == 7777.25
    assert result["expected_move"] == 68.12
    assert result["trade_setup"] is not None


def test_live_market_explicit_spx(monkeypatch):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    result = market_service.get_live_market("spx")

    assert result["underlying"] == "SPX"
    assert result["price"] == 7777.25


def test_qqq_uses_its_own_expected_move(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert result["underlying"] == "QQQ"
    assert result["price"] == 719.74

    assert (
        result["expected_move_available"]
        is True
    )
    assert result["expected_move"] == 6.70
    assert result["expected_move_pct"] == 0.93
    assert result["atm_strike"] == 720.0
    assert result["atm_call_mid"] == 3.50
    assert result["atm_put_mid"] == 3.20

    assert (
        result["expected_move_source"]
        == "OPTION_CHAIN_ATM_STRADDLE"
    )

    assert (
        result["expected_move_reason_code"]
        == "OPTION_CHAIN_EXPECTED_MOVE_READY"
    )


def test_qqq_remains_execution_blocked_when_em_ready(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert result["trade_setup"] is None
    assert result["signal_ready"] is False
    assert result["execution_enabled"] is False

    assert (
        result["reason_code"]
        == "QQQ_STABILITY_OBSERVING_EXECUTION_BLOCKED"
    )


def test_qqq_does_not_inherit_spx_trade_setup(
    monkeypatch,
):
    payload = _market_payload()

    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: payload,
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert payload["expected_move"] == 68.12
    assert payload["trade_setup"] is not None

    assert result["expected_move"] == 6.70
    assert result["trade_setup"] is None


def test_qqq_positions_are_symbol_scoped(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert len(result["positions"]) == 2
    assert len(
        result["underlying_positions"]
    ) == 1

    assert (
        result["underlying_positions"][0][
            "underlying"
        ]
        == "QQQ"
    )


def test_qqq_expected_move_failure_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: {
            "available": False,
            "signal_ready": False,
            "expected_move": None,
            "expected_move_pct": None,
            "atm_strike": None,
            "call_mid": None,
            "put_mid": None,
            "expiration": None,
            "dte": 0,
            "source": (
                "OPTION_CHAIN_ATM_STRADDLE"
            ),
            "reason_code": (
                "OPTION_CHAIN_UNAVAILABLE"
            ),
        },
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert (
        result["expected_move_available"]
        is False
    )
    assert result["expected_move"] is None
    assert result["signal_ready"] is False
    assert result["execution_enabled"] is False
    assert (
        result["reason_code"]
        == "OPTION_CHAIN_UNAVAILABLE"
    )


def test_qqq_expected_move_exception_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    def explode(*args, **kwargs):
        raise RuntimeError(
            "simulated option-chain failure"
        )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        explode,
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert result["expected_move"] is None
    assert result["signal_ready"] is False
    assert result["execution_enabled"] is False
    assert (
        result["reason_code"]
        == "QQQ_EXPECTED_MOVE_ERROR"
    )


def test_unknown_underlying_fails_closed():
    with pytest.raises(
        ValueError,
        match="Unsupported underlying",
    ):
        market_service.get_live_market("IWM")


def test_route_rejects_unknown_underlying():
    with pytest.raises(HTTPException) as exc:
        market_route.live_market("IWM")

    assert exc.value.status_code == 400

    assert "Unsupported underlying" in str(
        exc.value.detail
    )


def test_qqq_stability_pipeline_is_live(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    stability = result[
        "condor_stability"
    ]

    pressure = result[
        "range_expansion_pressure"
    ]

    score = result[
        "stability_score_detail"
    ]

    assert stability["available"] is True
    assert stability["signal_ready"] is True

    assert (
        stability["expected_move_source"]
        == "OPTION_CHAIN_ATM_STRADDLE"
    )

    assert result[
        "stability_signal_ready"
    ] is True

    assert result["session_phase"] == "EARLY"
    assert result["minutes_since_open"] == 60

    assert pressure["available"] is True
    assert pressure["pressure_ratio"] is not None

    assert score["available"] is True
    assert score["score"] is not None


def test_qqq_stability_does_not_enable_execution(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    # Stability can be ready without the QQQ trade
    # engine being authorized.
    assert (
        result["stability_signal_ready"]
        is True
    )

    assert result["signal_ready"] is False
    assert result["execution_enabled"] is False
    assert result["trade_setup"] is None

    assert (
        result["reason_code"]
        == "QQQ_STABILITY_OBSERVING_EXECUTION_BLOCKED"
    )


def test_qqq_candidate_preview_is_exposed(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert (
        result["candidate_preview_available"]
        is True
    )

    assert (
        result["candidate_pricing_ready"]
        is True
    )

    trade = result["candidate_preview"]

    assert trade["underlying"] == "QQQ"
    assert trade["sell_put"] == 712.0
    assert trade["buy_put"] == 707.0
    assert trade["sell_call"] == 720.0
    assert trade["buy_call"] == 725.0

    assert trade["wing_width"] == 5.0
    assert trade["live_credit"] == 1.25
    assert trade["max_risk"] == 375.0


def test_qqq_candidate_never_enables_execution(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert (
        result["candidate_observation_only"]
        is True
    )

    assert (
        result["candidate_execution_enabled"]
        is False
    )

    assert result["signal_ready"] is False
    assert result["execution_enabled"] is False
    assert result["trade_setup"] is None


def test_qqq_candidate_preview_failure_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        market_service.market_engine,
        "update",
        lambda: _market_payload(),
    )

    monkeypatch.setattr(
        market_service,
        "calculate_atm_straddle_expected_move",
        lambda *args, **kwargs: (
            _expected_move_ready()
        ),
    )

    def explode(*args, **kwargs):
        raise RuntimeError(
            "simulated candidate failure"
        )

    monkeypatch.setattr(
        market_service,
        "build_and_price_underlying_condor",
        explode,
    )

    result = market_service.get_live_market(
        "QQQ"
    )

    assert (
        result["candidate_preview_available"]
        is False
    )

    assert (
        result["candidate_pricing_ready"]
        is False
    )

    assert result["candidate_preview"] is None

    assert (
        result["candidate_reason_code"]
        == "CONDOR_PREVIEW_ERROR"
    )

    assert result["execution_enabled"] is False
