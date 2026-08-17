from bxk_app.condor_stability import (
    calculate_condor_stability_metrics,
)


def test_condor_stability_directional_move():
    result = calculate_condor_stability_metrics(
        spx_price=7835,
        expected_move=50,
        session_open=7800,
        day_high=7840,
        day_low=7795,
        prev_close=7790,
    )

    assert result["available"] is True
    assert result["session_range"] == 45.0
    assert result["upside_excursion"] == 40.0
    assert result["downside_excursion"] == 5.0
    assert result["max_directional_excursion"] == 40.0
    assert result["directional_consumed_pct"] == 80.0
    assert result["range_band_consumed_pct"] == 45.0
    assert result["current_displacement_pct"] == 70.0
    assert result["overnight_gap"] == 10.0
    assert result["overnight_gap_pct"] == 20.0


def test_condor_stability_two_sided_chop():
    result = calculate_condor_stability_metrics(
        spx_price=7800,
        expected_move=50,
        session_open=7800,
        day_high=7825,
        day_low=7775,
        prev_close=7800,
    )

    assert result["session_range"] == 50.0

    # Fifty points of total chop is NOT the same thing
    # as a fifty-point directional move.
    assert result["max_directional_excursion"] == 25.0
    assert result["directional_consumed_pct"] == 50.0
    assert result["range_band_consumed_pct"] == 50.0


def test_condor_stability_unavailable_without_required_data():
    result = calculate_condor_stability_metrics(
        spx_price=7800,
        expected_move=0,
        session_open=7800,
        day_high=7810,
        day_low=7790,
    )

    assert result["available"] is False
    assert result["signal_ready"] is False
    assert result["state"] == "UNAVAILABLE"
    assert result["reason_code"] == "STABILITY_DATA_UNAVAILABLE"
    assert result["expected_move_source"] == "VIX1D"
    assert result["market_status"] == "LIVE"



def test_condor_stability_allows_live_vix_fallback():
    result = calculate_condor_stability_metrics(
        spx_price=7780,
        expected_move=73.5,
        session_open=7790,
        day_high=7792,
        day_low=7775,
        prev_close=7785,
        expected_move_source="VIX",
        market_status="LIVE",
    )

    assert result["available"] is True
    assert result["signal_ready"] is True
    assert result["state"] == "OBSERVING"
    assert result["reason_code"] == "VIX_FALLBACK_ACTIVE"
    assert result["expected_move_source"] == "VIX"
    assert result["market_status"] == "LIVE"


def test_condor_stability_not_ready_when_market_closed():
    result = calculate_condor_stability_metrics(
        spx_price=7780,
        expected_move=73.5,
        session_open=7790,
        day_high=7792,
        day_low=7775,
        prev_close=7785,
        expected_move_source="VIX1D",
        market_status="CLOSED",
    )

    assert result["available"] is True
    assert result["signal_ready"] is False
    assert result["reason_code"] == "MARKET_NOT_LIVE"
