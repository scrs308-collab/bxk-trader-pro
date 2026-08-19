from bxk_app.qqq_stability import (
    calculate_qqq_stability_metrics,
)


def test_qqq_stability_metrics_are_calculated():
    result = calculate_qqq_stability_metrics(
        qqq_price=715.74,
        expected_move=4.21,
        session_open=720.39,
        day_high=721.50,
        day_low=715.50,
        prev_close=717.51,
        expected_move_source=(
            "OPTION_CHAIN_ATM_STRADDLE"
        ),
        market_status="LIVE",
    )

    assert result["available"] is True
    assert result["signal_ready"] is True
    assert result["underlying"] == "QQQ"

    assert result["qqq_price"] == 715.74
    assert result["implied_move"] == 4.21

    assert result["session_range"] == 6.0
    assert result["upside_excursion"] == 1.11
    assert result["downside_excursion"] == 4.89

    assert (
        result["max_directional_excursion"]
        == 4.89
    )

    assert result["current_displacement"] == 4.65

    assert (
        result["directional_consumed_pct"]
        > 100
    )

    assert (
        result["reason_code"]
        == "QQQ_STABILITY_METRICS_AVAILABLE"
    )


def test_qqq_stability_requires_option_chain_em():
    result = calculate_qqq_stability_metrics(
        qqq_price=715.74,
        expected_move=4.21,
        session_open=720.39,
        day_high=721.50,
        day_low=715.50,
        prev_close=717.51,
        expected_move_source="VIX1D",
        market_status="LIVE",
    )

    assert result["available"] is True
    assert result["signal_ready"] is False

    assert (
        result["reason_code"]
        == "QQQ_OPTION_CHAIN_EM_UNAVAILABLE"
    )


def test_qqq_stability_not_ready_when_closed():
    result = calculate_qqq_stability_metrics(
        qqq_price=715.74,
        expected_move=4.21,
        session_open=720.39,
        day_high=721.50,
        day_low=715.50,
        prev_close=717.51,
        expected_move_source=(
            "OPTION_CHAIN_ATM_STRADDLE"
        ),
        market_status="CLOSED",
    )

    assert result["available"] is True
    assert result["signal_ready"] is False
    assert (
        result["reason_code"]
        == "MARKET_NOT_LIVE"
    )


def test_qqq_stability_fails_closed_without_em():
    result = calculate_qqq_stability_metrics(
        qqq_price=715.74,
        expected_move=None,
        session_open=720.39,
        day_high=721.50,
        day_low=715.50,
        prev_close=717.51,
        expected_move_source=(
            "OPTION_CHAIN_ATM_STRADDLE"
        ),
        market_status="LIVE",
    )

    assert result["available"] is False
    assert result["signal_ready"] is False

    assert (
        result["reason_code"]
        == "QQQ_STABILITY_DATA_UNAVAILABLE"
    )
