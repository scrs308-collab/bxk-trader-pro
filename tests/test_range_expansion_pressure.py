from bxk_app.range_expansion_pressure import (
    calculate_range_expansion_pressure,
)


def test_pressure_at_1000():
    result = calculate_range_expansion_pressure(
        directional_consumed_pct=55,
        minutes_since_open=30,
        session_phase="EARLY",
        signal_ready=True,
    )

    assert result["available"] is True
    assert result["state"] == "OBSERVING"

    # sqrt(30 / 390) ~= 27.7%
    assert result["expected_pace_pct"] == 27.7

    # 55 / 27.7 ~= 1.98x
    assert result["pressure_ratio"] == 1.98
    assert result["pace_delta_pct"] == 27.3


def test_near_normal_pressure_at_1030():
    result = calculate_range_expansion_pressure(
        directional_consumed_pct=40,
        minutes_since_open=60,
        session_phase="EARLY",
        signal_ready=True,
    )

    assert result["available"] is True
    assert result["expected_pace_pct"] == 39.2
    assert result["pressure_ratio"] == 1.02
    assert result["pace_delta_pct"] == 0.8


def test_pressure_requires_ready_signal():
    result = calculate_range_expansion_pressure(
        directional_consumed_pct=50,
        minutes_since_open=30,
        session_phase="EARLY",
        signal_ready=False,
    )

    assert result["available"] is False
    assert result["reason_code"] == "SIGNAL_NOT_READY"


def test_pressure_rejects_closed_market():
    result = calculate_range_expansion_pressure(
        directional_consumed_pct=50,
        minutes_since_open=None,
        session_phase="CLOSED",
        signal_ready=True,
    )

    assert result["available"] is False
    assert result["reason_code"] == "MARKET_NOT_LIVE"


def test_pressure_has_opening_warmup():
    result = calculate_range_expansion_pressure(
        directional_consumed_pct=20,
        minutes_since_open=3,
        session_phase="OPENING",
        signal_ready=True,
    )

    assert result["available"] is False
    assert result["state"] == "WARMUP"
    assert result["reason_code"] == "OPENING_WARMUP"
