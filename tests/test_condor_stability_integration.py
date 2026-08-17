import pytest

import bxk_app.market_engine as market_engine_module

from bxk_app.market_data import MarketData


@pytest.fixture(autouse=True)
def disable_real_condor_logger(monkeypatch):
    """
    Integration tests must never write into the real
    Condor Stability history directory.
    """

    monkeypatch.setattr(
        market_engine_module,
        "log_condor_stability",
        lambda _market: {
            "logged": False,
            "reason": "TEST_LOG_DISABLED",
        },
    )


def test_live_market_exposes_condor_stability(monkeypatch):
    fresh_market_data = MarketData()

    monkeypatch.setattr(
        market_engine_module,
        "market_data",
        fresh_market_data,
    )

    monkeypatch.setattr(
        market_engine_module.broker,
        "authenticate",
        lambda: True,
    )

    engine = market_engine_module.MarketEngine()

    result = engine.update(
        spx={
            "last": "7835",
            "open": "7800",
            "day-high-price": "7840",
            "day-low-price": "7795",
            "prev-close": "7790",
        },
        vix={"last": "15"},
        vix1d={"last": "16"},
        qqq={},
        account={},
        positions=[],
    )

    stability = result["condor_stability"]

    assert stability["available"] is True
    assert stability["state"] == "OBSERVING"

    assert stability["spx_price"] == 7835.0
    assert stability["session_open"] == 7800.0
    assert stability["day_high"] == 7840.0
    assert stability["day_low"] == 7795.0

    assert stability["session_range"] == 45.0
    assert stability["max_directional_excursion"] == 40.0

    assert stability["implied_move"] > 0
    assert stability["directional_consumed_pct"] > 0

    snapshot = fresh_market_data.get_snapshot()

    assert "condor_stability" in snapshot
    assert snapshot["condor_stability"]["available"] is True


def test_market_engine_calls_stability_logger(
    monkeypatch,
):
    fresh_market_data = MarketData()
    calls = []

    monkeypatch.setattr(
        market_engine_module,
        "market_data",
        fresh_market_data,
    )

    monkeypatch.setattr(
        market_engine_module.broker,
        "authenticate",
        lambda: True,
    )

    def fake_log(market):
        calls.append(market)

        return {
            "logged": False,
            "reason": "TEST",
        }

    monkeypatch.setattr(
        market_engine_module,
        "log_condor_stability",
        fake_log,
    )

    engine = market_engine_module.MarketEngine()

    engine.update(
        spx={
            "last": "7835",
            "open": "7800",
            "day-high-price": "7840",
            "day-low-price": "7795",
            "prev-close": "7790",
        },
        vix={"last": "15"},
        vix1d={"last": "16"},
        qqq={},
        account={},
        positions=[],
    )

    assert calls == [fresh_market_data]

    assert (
        fresh_market_data
        .condor_stability["available"]
        is True
    )


def test_logger_failure_does_not_break_market_update(
    monkeypatch,
):
    fresh_market_data = MarketData()

    monkeypatch.setattr(
        market_engine_module,
        "market_data",
        fresh_market_data,
    )

    monkeypatch.setattr(
        market_engine_module.broker,
        "authenticate",
        lambda: True,
    )

    def broken_logger(_market):
        raise RuntimeError("simulated logger failure")

    monkeypatch.setattr(
        market_engine_module,
        "log_condor_stability",
        broken_logger,
    )

    engine = market_engine_module.MarketEngine()

    result = engine.update(
        spx={
            "last": "7835",
            "open": "7800",
            "day-high-price": "7840",
            "day-low-price": "7795",
            "prev-close": "7790",
        },
        vix={"last": "15"},
        vix1d={"last": "16"},
        qqq={},
        account={},
        positions=[],
    )

    assert result["spx"] == 7835.0

    assert (
        result["condor_stability"]["available"]
        is True
    )


def test_live_market_exposes_expansion_pressure(
    monkeypatch,
):
    fresh_market_data = MarketData()

    monkeypatch.setattr(
        fresh_market_data,
        "market_status",
        lambda: "LIVE",
    )

    monkeypatch.setattr(
        market_engine_module,
        "market_data",
        fresh_market_data,
    )

    monkeypatch.setattr(
        market_engine_module.broker,
        "authenticate",
        lambda: True,
    )

    monkeypatch.setattr(
        market_engine_module,
        "get_market_session_phase",
        lambda: {
            "session_phase": "EARLY",
            "minutes_since_open": 30,
        },
    )

    engine = market_engine_module.MarketEngine()

    result = engine.update(
        spx={
            "last": "7835",
            "open": "7800",
            "day-high-price": "7840",
            "day-low-price": "7795",
            "prev-close": "7790",
        },
        vix={"last": "15"},
        vix1d={"last": "16"},
        qqq={},
        account={},
        positions=[],
    )

    stability = result["condor_stability"]

    assert stability["session_phase"] == "EARLY"
    assert stability["minutes_since_open"] == 30

    pressure = (
        stability["range_expansion_pressure"]
    )

    assert pressure["available"] is True
    assert pressure["state"] == "OBSERVING"
    assert pressure["expected_pace_pct"] == 27.7
    assert pressure["pressure_ratio"] > 0


def test_live_market_exposes_provisional_stability_score(
    monkeypatch,
):
    fresh_market_data = MarketData()

    monkeypatch.setattr(
        fresh_market_data,
        "market_status",
        lambda: "LIVE",
    )

    monkeypatch.setattr(
        market_engine_module,
        "market_data",
        fresh_market_data,
    )

    monkeypatch.setattr(
        market_engine_module.broker,
        "authenticate",
        lambda: True,
    )

    monkeypatch.setattr(
        market_engine_module,
        "get_market_session_phase",
        lambda: {
            "session_phase": "EARLY",
            "minutes_since_open": 30,
        },
    )

    engine = market_engine_module.MarketEngine()

    result = engine.update(
        spx={
            "last": "7835",
            "open": "7800",
            "day-high-price": "7840",
            "day-low-price": "7795",
            "prev-close": "7790",
        },
        vix={"last": "15"},
        vix1d={"last": "16"},
        qqq={},
        account={},
        positions=[],
    )

    score = (
        result["condor_stability"]
        ["stability_score"]
    )

    assert score["available"] is True
    assert score["state"] == "OBSERVING"

    assert 0 <= score["score"] <= 100
    assert score["total_penalty"] >= 0

    assert "components" in score

    assert (
        "expansion_pressure"
        in score["components"]
    )
