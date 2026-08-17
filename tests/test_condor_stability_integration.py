import bxk_app.market_engine as market_engine_module

from bxk_app.market_data import MarketData


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
