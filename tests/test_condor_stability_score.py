from bxk_app.condor_stability_score import (
    calculate_condor_stability_score,
)


def test_stable_environment_scores_high():
    result = calculate_condor_stability_score(
        signal_ready=True,
        directional_consumed_pct=25,
        current_displacement_pct=12,
        range_band_consumed_pct=18,
        overnight_gap_pct=5,
        pressure_ratio=0.90,
    )

    assert result["available"] is True
    assert result["state"] == "OBSERVING"

    assert result["score"] > 90


def test_expanding_environment_scores_lower():
    result = calculate_condor_stability_score(
        signal_ready=True,
        directional_consumed_pct=70,
        current_displacement_pct=60,
        range_band_consumed_pct=55,
        overnight_gap_pct=20,
        pressure_ratio=1.80,
    )

    assert result["available"] is True

    assert 25 < result["score"] < 65

    assert (
        result["components"]
        ["expansion_pressure"]
        ["penalty"]
        > 20
    )


def test_hostile_environment_scores_very_low():
    result = calculate_condor_stability_score(
        signal_ready=True,
        directional_consumed_pct=110,
        current_displacement_pct=105,
        range_band_consumed_pct=90,
        overnight_gap_pct=80,
        pressure_ratio=2.40,
    )

    assert result["available"] is True
    assert result["score"] == 0.0
    assert result["total_penalty"] == 100.0


def test_score_requires_ready_signal():
    result = calculate_condor_stability_score(
        signal_ready=False,
        directional_consumed_pct=40,
        current_displacement_pct=20,
        range_band_consumed_pct=25,
        overnight_gap_pct=10,
        pressure_ratio=1.00,
    )

    assert result == {
        "available": False,
        "state": "UNAVAILABLE",
        "reason_code": "SIGNAL_NOT_READY",
        "score": None,
    }


def test_score_requires_core_inputs():
    result = calculate_condor_stability_score(
        signal_ready=True,
        directional_consumed_pct=None,
        current_displacement_pct=20,
        range_band_consumed_pct=25,
        overnight_gap_pct=10,
        pressure_ratio=1.00,
    )

    assert result["available"] is False

    assert (
        result["reason_code"]
        == "STABILITY_INPUTS_UNAVAILABLE"
    )

    assert result["score"] is None


def test_overnight_gap_is_optional():
    result = calculate_condor_stability_score(
        signal_ready=True,
        directional_consumed_pct=30,
        current_displacement_pct=20,
        range_band_consumed_pct=20,
        overnight_gap_pct=None,
        pressure_ratio=1.00,
    )

    assert result["available"] is True

    assert (
        result["components"]
        ["overnight_gap"]
        ["value"]
        == 0.0
    )
