def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def grade_trade(score: int):
    if score >= 95:
        return "A+", "Elite"

    if score >= 90:
        return "A", "Excellent"

    if score >= 85:
        return "A-", "Strong"

    if score >= 80:
        return "B+", "Good"

    if score >= 75:
        return "B", "Acceptable"

    if score >= 70:
        return "C", "Fair"

    if score >= 60:
        return "D", "Weak"

    return "F", "Poor"


def analyze_trade(trade: dict):
    """
    Score the trade structure separately from market permission.

    Trade Quality Score:
        Credit quality         20 points
        Probability of profit  25 points
        Probability of touch   20 points
        Risk / reward          15 points
        Wing width             10 points
        Structural balance     10 points

    Maximum trade quality score = 100
    """

    score = 0
    strengths = []
    weaknesses = []
    reasons = []

    credit = safe_float(
        trade.get("credit"),
        0,
    )

    pop = safe_float(
        trade.get("pop"),
        0,
    )

    touch_raw = trade.get(
        "probability_of_touch"
    )

    if touch_raw is None:
        touch_raw = trade.get(
            "touch_probability"
        )

    touch = (
    safe_float(touch_raw)
    if touch_raw is not None
    else None
)

    # Fall back to a POP-based estimate when live deltas
    # are unavailable, such as after market hours.
    if touch is None and pop > 0:
        touch = min(
            100,
            round(
                2 * (100 - pop),
                1,
            ),
        )

    risk_reward = safe_float(
        trade.get("risk_reward"),
        99,
    )

    wing_width = int(
        safe_float(
            trade.get("wing_width"),
            25,
        )
    )

    put_distance = safe_float(
        trade.get(
            "put_distance",
            trade.get("put_buffer"),
        ),
        0,
    )

    call_distance = safe_float(
        trade.get(
            "call_distance",
            trade.get("call_buffer"),
        ),
        0,
    )

    market_regime = str(
        trade.get(
            "market_regime",
            "WAIT",
        )
    ).upper()

    market_score = safe_float(
        trade.get("market_score"),
        0,
    )

    # =====================================================
    # CREDIT QUALITY - 20 POINTS
    # =====================================================

    if credit >= 3.00:
        score += 20
        strengths.append(
            {
                "reason": "Premium exceeds target",
                "impact": 20,
            }
        )

    elif credit >= 2.50:
        score += 17
        strengths.append(
            {
                "reason": "Premium is strong",
                "impact": 17,
            }
        )

    elif credit >= 2.00:
        score += 14
        strengths.append(
            {
                "reason": "Premium is acceptable",
                "impact": 14,
            }
        )

    elif credit >= 1.50:
        score += 9
        weaknesses.append(
            {
                "reason": "Premium is below preferred target",
                "impact": -11,
            }
        )

    else:
        score += 3
        weaknesses.append(
            {
                "reason": "Premium is too low",
                "impact": -17,
            }
        )

    # =====================================================
    # PROBABILITY OF PROFIT - 25 POINTS
    # =====================================================

    if pop >= 90:
        score += 25
        strengths.append(
            {
                "reason": f"Excellent probability of profit at {pop:.1f}%",
                "impact": 25,
            }
        )

    elif pop >= 85:
        score += 22
        strengths.append(
            {
                "reason": f"Strong probability of profit at {pop:.1f}%",
                "impact": 22,
            }
        )

    elif pop >= 80:
        score += 18
        strengths.append(
            {
                "reason": f"Good probability of profit at {pop:.1f}%",
                "impact": 18,
            }
        )

    elif pop >= 75:
        score += 13
        weaknesses.append(
            {
                "reason": f"Probability of profit is only {pop:.1f}%",
                "impact": -12,
            }
        )

    else:
        score += 5
        weaknesses.append(
            {
                "reason": f"Probability of profit is too low at {pop:.1f}%",
                "impact": -20,
            }
        )

    # =====================================================
    # PROBABILITY OF TOUCH - 20 POINTS
    # =====================================================

    if touch is None:
        weaknesses.append(
            {
                "reason": "Touch probability unavailable",
                "impact": 0,
            }
        )

    elif touch <= 20:
        score += 20
        strengths.append(
            {
                "reason": f"Very low touch probability at {touch:.1f}%",
                "impact": 20,
            }
        )

    elif touch <= 30:
        score += 17
        strengths.append(
            {
                "reason": f"Low touch probability at {touch:.1f}%",
                "impact": 17,
            }
        )

    elif touch <= 40:
        score += 13
        strengths.append(
            {
                "reason": f"Acceptable touch probability at {touch:.1f}%",
                "impact": 13,
            }
        )

    elif touch <= 50:
        score += 7
        weaknesses.append(
            {
                "reason": f"Touch probability is elevated at {touch:.1f}%",
                "impact": -13,
            }
        )

    else:
        score += 2
        weaknesses.append(
            {
                "reason": f"Touch probability is too high at {touch:.1f}%",
                "impact": -18,
            }
        )

    # =====================================================
    # RISK / REWARD - 15 POINTS
    # =====================================================

    if risk_reward <= 8:
        score += 15
        strengths.append(
            {
                "reason": f"Risk / reward is strong at 1:{risk_reward:.2f}",
                "impact": 15,
            }
        )

    elif risk_reward <= 10:
        score += 12
        strengths.append(
            {
                "reason": f"Risk / reward is acceptable at 1:{risk_reward:.2f}",
                "impact": 12,
            }
        )

    elif risk_reward <= 12:
        score += 8
        weaknesses.append(
            {
                "reason": f"Risk / reward is marginal at 1:{risk_reward:.2f}",
                "impact": -7,
            }
        )

    elif risk_reward <= 15:
        score += 4
        weaknesses.append(
            {
                "reason": f"Risk / reward is weak at 1:{risk_reward:.2f}",
                "impact": -11,
            }
        )

    else:
        weaknesses.append(
            {
                "reason": f"Risk / reward is poor at 1:{risk_reward:.2f}",
                "impact": -15,
            }
        )

    # =====================================================
    # WING WIDTH - 10 POINTS
    # =====================================================

    if wing_width == 25:
        score += 10
        strengths.append(
            {
                "reason": "Preferred 25-point wing width",
                "impact": 10,
            }
        )

    elif wing_width == 20:
        score += 8
        strengths.append(
            {
                "reason": "Good 20-point wing width",
                "impact": 8,
            }
        )

    elif wing_width in (10, 15):
        score += 5
        weaknesses.append(
            {
                "reason": f"{wing_width}-point wings provide less flexibility",
                "impact": -5,
            }
        )

    else:
        score += 3
        weaknesses.append(
            {
                "reason": f"Non-preferred wing width of {wing_width}",
                "impact": -7,
            }
        )

    # =====================================================
    # STRUCTURAL BALANCE - 10 POINTS
    # =====================================================

    if put_distance > 0 and call_distance > 0:
        distance_difference = abs(
            put_distance - call_distance
        )

        if distance_difference <= 5:
            score += 10
            strengths.append(
                {
                    "reason": "Call and put buffers are well balanced",
                    "impact": 10,
                }
            )

        elif distance_difference <= 10:
            score += 8
            strengths.append(
                {
                    "reason": "Trade structure is reasonably balanced",
                    "impact": 8,
                }
            )

        elif distance_difference <= 20:
            score += 5
            weaknesses.append(
                {
                    "reason": "Trade structure is moderately unbalanced",
                    "impact": -5,
                }
            )

        else:
            score += 2
            weaknesses.append(
                {
                    "reason": "Call and put buffers are significantly unbalanced",
                    "impact": -8,
                }
            )

    else:
        score += 5
        weaknesses.append(
            {
                "reason": "Buffer balance could not be measured",
                "impact": -5,
            }
        )

    score = max(
        0,
        min(
            100,
            round(score),
        ),
    )

    grade, rating = grade_trade(score)

    # =====================================================
    # MARKET PERMISSION
    # =====================================================

    if market_regime == "TRADE":
        market_permission = "TRADE"
        permission_label = "Market supports entry"

    elif market_regime == "CAUTION":
        market_permission = "CAUTION"
        permission_label = "Market permits reduced size only"

    else:
        market_permission = "WAIT"
        permission_label = "Market does not support entry"

    # =====================================================
    # FINAL DECISION
    # =====================================================

    if (
        market_permission == "TRADE"
        and score >= 80
    ):
        final_decision = "ENTER TRADE"

    elif (
        market_permission == "CAUTION"
        and score >= 85
    ):
        final_decision = "TRADE SMALL"

    else:
        final_decision = "NO TRADE"

    reasons.extend(
        item["reason"]
        for item in strengths
    )

    reasons.extend(
        item["reason"]
        for item in weaknesses
    )

    return {
        # Compatibility: dashboard already reads trade_score
        "trade_score": score,

        # New clearer name
        "trade_quality_score": score,

        "grade": grade,
        "rating": rating,
        "quality_label": f"{grade} {rating}",

        "market_score": round(
            market_score,
        ),
        "market_permission": market_permission,
        "permission_label": permission_label,

        "final_decision": final_decision,

        "strengths": strengths,
        "weaknesses": weaknesses,
        "reasons": reasons,
    }