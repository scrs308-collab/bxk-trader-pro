def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, low=0.0, high=1.0):
    return max(
        low,
        min(high, value),
    )


def _scaled_risk(
    value,
    *,
    low,
    high,
):
    """
    Convert a measurement into a 0.0 - 1.0 risk value.

    At or below low:
        risk = 0

    At or above high:
        risk = 1

    Between:
        linearly interpolated
    """

    number = _safe_float(value)

    if number is None:
        return None

    if high <= low:
        raise ValueError(
            "high must be greater than low"
        )

    return _clamp(
        (number - low) /
        (high - low)
    )


def calculate_condor_stability_score(
    *,
    signal_ready,
    directional_consumed_pct,
    current_displacement_pct,
    range_band_consumed_pct,
    overnight_gap_pct,
    pressure_ratio,
):
    """
    Produce a PROVISIONAL iron-condor stability score.

    100 = more stable
      0 = more hostile

    This score is observation-only.

    It does NOT authorize, block, size, or submit trades.

    Thresholds are intentionally provisional until BXK
    accumulates enough real session history for calibration.
    """

    if signal_ready is not True:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "reason_code": "SIGNAL_NOT_READY",
            "score": None,
        }

    pressure = _safe_float(
        pressure_ratio
    )

    directional = _safe_float(
        directional_consumed_pct
    )

    displacement = _safe_float(
        current_displacement_pct
    )

    range_used = _safe_float(
        range_band_consumed_pct
    )

    overnight_gap = _safe_float(
        overnight_gap_pct
    )

    required = (
        pressure,
        directional,
        displacement,
        range_used,
    )

    if any(
        value is None
        for value in required
    ):
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "reason_code":
                "STABILITY_INPUTS_UNAVAILABLE",
            "score": None,
        }

    # -----------------------------------------------------
    # PROVISIONAL NORMALIZATION
    #
    # Pressure:
    # <= 0.80x   little/no penalty
    # >= 2.00x   full pressure penalty
    #
    # Directional consumption:
    # <= 20%     little/no penalty
    # >= 100%    full penalty
    #
    # Current displacement:
    # <= 10%     little/no penalty
    # >= 100%    full penalty
    #
    # Range band:
    # <= 15%     little/no penalty
    # >= 80%     full penalty
    #
    # Overnight gap:
    # <= 10%     little/no penalty
    # >= 75%     full penalty
    # -----------------------------------------------------

    pressure_risk = _scaled_risk(
        pressure,
        low=0.80,
        high=2.00,
    )

    directional_risk = _scaled_risk(
        directional,
        low=20.0,
        high=100.0,
    )

    displacement_risk = _scaled_risk(
        displacement,
        low=10.0,
        high=100.0,
    )

    range_risk = _scaled_risk(
        range_used,
        low=15.0,
        high=80.0,
    )

    gap_risk = _scaled_risk(
        overnight_gap or 0.0,
        low=10.0,
        high=75.0,
    )

    component_penalties = {
        "expansion_pressure": round(
            pressure_risk * 35.0,
            2,
        ),
        "directional_consumption": round(
            directional_risk * 25.0,
            2,
        ),
        "current_displacement": round(
            displacement_risk * 20.0,
            2,
        ),
        "range_consumption": round(
            range_risk * 15.0,
            2,
        ),
        "overnight_gap": round(
            gap_risk * 5.0,
            2,
        ),
    }

    total_penalty = sum(
        component_penalties.values()
    )

    score = round(
        max(
            0.0,
            100.0 - total_penalty,
        ),
        1,
    )

    return {
        "available": True,
        "state": "OBSERVING",
        "reason_code":
            "PROVISIONAL_SCORE_AVAILABLE",
        "score": score,
        "total_penalty": round(
            total_penalty,
            1,
        ),
        "components": {
            "expansion_pressure": {
                "value": round(
                    pressure,
                    2,
                ),
                "weight": 35,
                "penalty":
                    component_penalties[
                        "expansion_pressure"
                    ],
            },
            "directional_consumption": {
                "value": round(
                    directional,
                    1,
                ),
                "weight": 25,
                "penalty":
                    component_penalties[
                        "directional_consumption"
                    ],
            },
            "current_displacement": {
                "value": round(
                    displacement,
                    1,
                ),
                "weight": 20,
                "penalty":
                    component_penalties[
                        "current_displacement"
                    ],
            },
            "range_consumption": {
                "value": round(
                    range_used,
                    1,
                ),
                "weight": 15,
                "penalty":
                    component_penalties[
                        "range_consumption"
                    ],
            },
            "overnight_gap": {
                "value": round(
                    overnight_gap or 0.0,
                    1,
                ),
                "weight": 5,
                "penalty":
                    component_penalties[
                        "overnight_gap"
                    ],
            },
        },
    }
