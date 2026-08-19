from bxk_app.underlying_stability import (
    calculate_underlying_stability_metrics,
)


def test_spy_stability_metrics():
    result = (
        calculate_underlying_stability_metrics(
            symbol="SPY",
            underlying_price=100.0,
            expected_move=4.0,
            session_open=99.0,
            day_high=101.0,
            day_low=98.0,
            prev_close=98.5,
            expected_move_source=(
                "OPTION_CHAIN_ATM_STRADDLE"
            ),
            market_status="LIVE",
        )
    )

    assert result["available"] is True
    assert result["signal_ready"] is True

    assert result["underlying"] == "SPY"

    assert (
        result["reason_code"]
        == "STABILITY_METRICS_AVAILABLE"
    )

    assert result["underlying_price"] == 100.0

    assert result["session_range"] == 3.0
    assert result["upside_excursion"] == 2.0
    assert result["downside_excursion"] == 1.0

    assert (
        result["max_directional_excursion"]
        == 2.0
    )

    assert (
        result["directional_consumed_pct"]
        == 50.0
    )

    assert (
        result["range_band_consumed_pct"]
        == 37.5
    )

    assert (
        result["current_displacement_pct"]
        == 25.0
    )

    assert result["overnight_gap"] == 0.5
    assert result["overnight_gap_pct"] == 12.5


def test_market_not_live_is_not_signal_ready():
    result = (
        calculate_underlying_stability_metrics(
            symbol="IWM",
            underlying_price=300,
            expected_move=5,
            session_open=299,
            day_high=301,
            day_low=298,
            prev_close=298,
            expected_move_source=(
                "OPTION_CHAIN_ATM_STRADDLE"
            ),
            market_status="CLOSED",
        )
    )

    assert result["available"] is True
    assert result["signal_ready"] is False

    assert (
        result["reason_code"]
        == "MARKET_NOT_LIVE"
    )


def test_wrong_expected_move_source_blocks_signal():
    result = (
        calculate_underlying_stability_metrics(
            symbol="DIA",
            underlying_price=535,
            expected_move=4,
            session_open=534,
            day_high=536,
            day_low=533,
            prev_close=532,
            expected_move_source="VIX",
            market_status="LIVE",
        )
    )

    assert result["available"] is True
    assert result["signal_ready"] is False

    assert (
        result["reason_code"]
        == "OPTION_CHAIN_EM_UNAVAILABLE"
    )


def test_missing_metrics_fail_closed():
    result = (
        calculate_underlying_stability_metrics(
            symbol="XSP",
            underlying_price=770,
            expected_move=4,
            session_open=None,
            day_high=772,
            day_low=768,
            prev_close=769,
            expected_move_source=(
                "OPTION_CHAIN_ATM_STRADDLE"
            ),
            market_status="LIVE",
        )
    )

    assert result["available"] is False
    assert result["signal_ready"] is False

    assert (
        result["reason_code"]
        == "STABILITY_DATA_UNAVAILABLE"
    )
