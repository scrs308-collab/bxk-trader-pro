from typing import List, Dict


def build_strategy(
    name: str,
    score: int,
    reason: str,
    factors: List[Dict] | None = None,
) -> Dict:

    normalized_score = max(
        0,
        min(score, 100),
    )

    status = (
        "APPROVED"
        if normalized_score >= 75
        else "CAUTION"
        if normalized_score >= 50
        else "DENIED"
    )

    confidence = (
        "High"
        if normalized_score >= 80
        else "Medium"
        if normalized_score >= 60
        else "Low"
    )
    return {
        "name": name,
        "score": normalized_score,
        "raw_score": score,
        "score_capped": score > 100,
        "status": status,
        "confidence": confidence,
        "reason": reason,
        "factors": factors or [],
    }

strategy_priority = {
    "Iron Condor": 6,
    "Bull Put Credit Spread": 5,
    "Bear Call Credit Spread": 4,
    "Debit Call Spread": 3,
    "Debit Put Spread": 2,
    "Butterfly": 1,
}


def rank_strategies(
    market_score: int,
    trend: str,
    vix_state: str,
) -> List[Dict]:

    strategies = []

        # ============================================
    # Iron Condor
    # ============================================

    score = market_score

    factors = [
        {
            "label": "Base market score",
            "points": market_score,
        },
    ]

    if vix_state == "IDEAL":
        score += 10

        factors.append(
            {
                "label": "Ideal VIX",
                "points": 10,
            }
        )

    if trend == "MIXED":
        score += 10

        factors.append(
            {
                "label": "Mixed trend",
                "points": 10,
            }
        )

    strategies.append(
        build_strategy(
            "Iron Condor",
            score,
            "Balanced market with healthy premium.",
            factors,
        )
    )

    # ============================================
    # Bull Put Credit Spread
    # ============================================

    score = 45

    factors = [
        {
            "label": "Base strategy score",
            "points": 45,
        },
    ]

    if trend == "BULL":
        score += 30

        factors.append(
            {
                "label": "Bullish trend",
                "points": 30,
            }
        )

    if vix_state == "IDEAL":
        score += 10

        factors.append(
            {
                "label": "Ideal VIX",
                "points": 10,
            }
        )

    strategies.append(
        build_strategy(
            "Bull Put Credit Spread",
            score,
            "Bullish conditions favor selling put premium.",
            factors,
        )
    )
        # ============================================
    # Bear Call Credit Spread
    # ============================================

    score = 45

    factors = [
        {
            "label": "Base strategy score",
            "points": 45,
        },
    ]

    if trend == "BEAR":
        score += 30

        factors.append(
            {
                "label": "Bearish trend",
                "points": 30,
            }
        )

    if vix_state == "IDEAL":
        score += 10

        factors.append(
            {
                "label": "Ideal VIX",
                "points": 10,
            }
        )

    strategies.append(
        build_strategy(
            "Bear Call Credit Spread",
            score,
            "Bearish conditions favor selling call premium.",
            factors,
        )
    )
        # ============================================
    # Debit Call
    # ============================================

    score = 35

    factors = [
        {
            "label": "Base strategy score",
            "points": 35,
        },
    ]

    if trend == "BULL":
        score += 35

        factors.append(
            {
                "label": "Bullish trend",
                "points": 35,
            }
        )

    strategies.append(
        build_strategy(
            "Debit Call Spread",
            score,
            "Directional bullish strategy.",
            factors,
        )
    )
        # ============================================
    # Debit Put
    # ============================================

    score = 35

    factors = [
        {
            "label": "Base strategy score",
            "points": 35,
        },
    ]

    if trend == "BEAR":
        score += 35

        factors.append(
            {
                "label": "Bearish trend",
                "points": 35,
            }
        )

    strategies.append(
        build_strategy(
            "Debit Put Spread",
            score,
            "Directional bearish strategy.",
            factors,
        )
    )
        # ============================================
    # Butterfly
    # ============================================

    score = 50

    factors = [
        {
            "label": "Base strategy score",
            "points": 50,
        },
    ]

    if trend == "MIXED":
        score += 20

        factors.append(
            {
                "label": "Mixed trend",
                "points": 20,
            }
        )

    strategies.append(
        build_strategy(
            "Butterfly",
            score,
            "Best near price magnets and low movement.",
            factors,
        )
    )
    

    strategies.sort(
        key=lambda s: (
            s["score"],
            strategy_priority.get(
                s["name"],
                0,
            ),
        ),
        reverse=True,
    )

    return strategies



# =========================================================
# Strategy Ranker V2
#
# Observation-only strategy-fit model.
#
# IMPORTANT:
# This model is currently used only by the dashboard
# Strategy Playbook. Scanner/order selection continues
# using rank_strategies() until V2 has been observed and
# validated through live sessions.
# =========================================================


def _strategy_number(
    value,
    default=None,
):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _strategy_adjust(
    scores,
    factors,
    strategy,
    label,
    points,
):
    scores[strategy] += points

    factors[strategy].append(
        {
            "label": label,
            "points": points,
        }
    )


def rank_strategies_v2(
    market_score: int,
    vix_state: str,
    *,
    current_price=None,
    condor_stability=None,
) -> List[Dict]:
    """
    Rank strategy FIT using live SPX intraday evidence.

    Observation only.

    This function does not build, authorize, size,
    validate, or submit an order.

    Direction is determined from current SPX versus
    the session open, normalized by the implied move.

    Expansion behavior comes from the existing
    Condor Stability / Range Expansion Pressure
    observation metrics.
    """

    stability = (
        condor_stability
        if isinstance(
            condor_stability,
            dict,
        )
        else {}
    )

    # Fail safely back to the legacy display model when
    # live stability evidence is unavailable.
    if (
        stability.get("available") is not True
        or stability.get("signal_ready") is not True
    ):
        fallback = rank_strategies(
            market_score,
            "MIXED",
            vix_state,
        )

        for item in fallback:
            item["model_version"] = (
                "V1_FALLBACK"
            )
            item["observation_only"] = True

        return fallback

    price = _strategy_number(
        stability.get("spx_price"),
        _strategy_number(
            current_price
        ),
    )

    session_open = _strategy_number(
        stability.get("session_open")
    )

    implied_move = _strategy_number(
        stability.get("implied_move")
    )

    if (
        price is None
        or session_open is None
        or implied_move is None
        or implied_move <= 0
    ):
        fallback = rank_strategies(
            market_score,
            "MIXED",
            vix_state,
        )

        for item in fallback:
            item["model_version"] = (
                "V1_FALLBACK"
            )
            item["observation_only"] = True

        return fallback

    market_quality = max(
        0.0,
        min(
            100.0,
            _strategy_number(
                market_score,
                0.0,
            ),
        ),
    )

    # General trade quality contributes at most 35 points.
    # This prevents a 94-100 market score from automatically
    # forcing every premium strategy near 100.
    quality_points = int(
        round(
            market_quality * 0.35
        )
    )

    names = [
        "Iron Condor",
        "Bull Put Credit Spread",
        "Bear Call Credit Spread",
        "Debit Call Spread",
        "Debit Put Spread",
        "Butterfly",
    ]

    base_scores = {
        "Iron Condor": 35,
        "Bull Put Credit Spread": 30,
        "Bear Call Credit Spread": 30,
        "Debit Call Spread": 20,
        "Debit Put Spread": 20,
        "Butterfly": 25,
    }

    scores = dict(base_scores)

    factors = {
        name: [
            {
                "label": "Base strategy fit",
                "points": base_scores[name],
            },
            {
                "label": "Live trade quality",
                "points": quality_points,
            },
        ]
        for name in names
    }

    for name in names:
        scores[name] += quality_points

    # -----------------------------------------------------
    # Premium environment
    # -----------------------------------------------------

    if str(vix_state or "").upper() == "IDEAL":
        for name, points in (
            ("Iron Condor", 10),
            ("Bull Put Credit Spread", 8),
            ("Bear Call Credit Spread", 8),
            ("Butterfly", 5),
        ):
            _strategy_adjust(
                scores,
                factors,
                name,
                "Ideal volatility environment",
                points,
            )

    # -----------------------------------------------------
    # Signed displacement from the session open
    #
    # This is the major difference from V1.
    # V1 receives trend=MIXED almost continuously.
    # -----------------------------------------------------

    signed_displacement_pct = (
        (
            price - session_open
        )
        / implied_move
        * 100.0
    )

    displacement_strength = abs(
        signed_displacement_pct
    )

    if displacement_strength < 10.0:
        direction_state = "NEUTRAL"

        _strategy_adjust(
            scores,
            factors,
            "Iron Condor",
            "Price remains near session open",
            10,
        )

        _strategy_adjust(
            scores,
            factors,
            "Butterfly",
            "Price remains near session open",
            12,
        )

    elif signed_displacement_pct > 0:
        direction_state = "BULLISH"

        if displacement_strength < 25.0:
            bull_credit = 8
            bull_debit = 5
            opposite_credit = -8
            opposite_debit = -5
            condor_points = 4
            butterfly_points = 3
            strength_label = "Mild bullish displacement"

        elif displacement_strength < 50.0:
            bull_credit = 18
            bull_debit = 15
            opposite_credit = -18
            opposite_debit = -15
            condor_points = -8
            butterfly_points = -10
            strength_label = "Moderate bullish displacement"

        else:
            # Strong directional expansion increasingly favors
            # defined-risk debit participation over neutral
            # premium selling.
            bull_credit = 12
            bull_debit = 25
            opposite_credit = -25
            opposite_debit = -25
            condor_points = -20
            butterfly_points = -18
            strength_label = "Strong bullish displacement"

        for name, points in (
            (
                "Bull Put Credit Spread",
                bull_credit,
            ),
            (
                "Debit Call Spread",
                bull_debit,
            ),
            (
                "Bear Call Credit Spread",
                opposite_credit,
            ),
            (
                "Debit Put Spread",
                opposite_debit,
            ),
            (
                "Iron Condor",
                condor_points,
            ),
            (
                "Butterfly",
                butterfly_points,
            ),
        ):
            _strategy_adjust(
                scores,
                factors,
                name,
                strength_label,
                points,
            )

    else:
        direction_state = "BEARISH"

        if displacement_strength < 25.0:
            bear_credit = 8
            bear_debit = 5
            opposite_credit = -8
            opposite_debit = -5
            condor_points = 4
            butterfly_points = 3
            strength_label = "Mild bearish displacement"

        elif displacement_strength < 50.0:
            bear_credit = 18
            bear_debit = 15
            opposite_credit = -18
            opposite_debit = -15
            condor_points = -8
            butterfly_points = -10
            strength_label = "Moderate bearish displacement"

        else:
            bear_credit = 12
            bear_debit = 25
            opposite_credit = -25
            opposite_debit = -25
            condor_points = -20
            butterfly_points = -18
            strength_label = "Strong bearish displacement"

        for name, points in (
            (
                "Bear Call Credit Spread",
                bear_credit,
            ),
            (
                "Debit Put Spread",
                bear_debit,
            ),
            (
                "Bull Put Credit Spread",
                opposite_credit,
            ),
            (
                "Debit Call Spread",
                opposite_debit,
            ),
            (
                "Iron Condor",
                condor_points,
            ),
            (
                "Butterfly",
                butterfly_points,
            ),
        ):
            _strategy_adjust(
                scores,
                factors,
                name,
                strength_label,
                points,
            )

    # -----------------------------------------------------
    # Intraday expansion pressure
    # -----------------------------------------------------

    pressure_data = stability.get(
        "range_expansion_pressure"
    )

    if not isinstance(
        pressure_data,
        dict,
    ):
        pressure_data = {}

    pressure_ratio = _strategy_number(
        pressure_data.get(
            "pressure_ratio"
        )
    )

    if pressure_ratio is not None:
        if pressure_ratio <= 0.80:
            for name, points in (
                ("Iron Condor", 10),
                ("Butterfly", 8),
                ("Debit Call Spread", -6),
                ("Debit Put Spread", -6),
            ):
                _strategy_adjust(
                    scores,
                    factors,
                    name,
                    "Contained expansion pace",
                    points,
                )

        elif pressure_ratio >= 1.60:
            for name, points in (
                ("Iron Condor", -20),
                ("Butterfly", -15),
                ("Debit Call Spread", 15),
                ("Debit Put Spread", 15),
                ("Bull Put Credit Spread", -8),
                ("Bear Call Credit Spread", -8),
            ):
                _strategy_adjust(
                    scores,
                    factors,
                    name,
                    "High expansion pressure",
                    points,
                )

        elif pressure_ratio >= 1.20:
            for name, points in (
                ("Iron Condor", -10),
                ("Butterfly", -8),
                ("Debit Call Spread", 8),
                ("Debit Put Spread", 8),
                ("Bull Put Credit Spread", -3),
                ("Bear Call Credit Spread", -3),
            ):
                _strategy_adjust(
                    scores,
                    factors,
                    name,
                    "Elevated expansion pressure",
                    points,
                )

    # -----------------------------------------------------
    # Total range consumption
    # -----------------------------------------------------

    range_used = _strategy_number(
        stability.get(
            "range_band_consumed_pct"
        )
    )

    if range_used is not None:
        if range_used <= 25.0:
            for name, points in (
                ("Iron Condor", 5),
                ("Butterfly", 8),
            ):
                _strategy_adjust(
                    scores,
                    factors,
                    name,
                    "Contained session range",
                    points,
                )

        elif range_used >= 60.0:
            for name, points in (
                ("Iron Condor", -10),
                ("Butterfly", -8),
                ("Debit Call Spread", 5),
                ("Debit Put Spread", 5),
            ):
                _strategy_adjust(
                    scores,
                    factors,
                    name,
                    "Broad session range",
                    points,
                )

    reasons = {
        "Iron Condor":
            "Neutral premium fit adjusted for live "
            "SPX displacement and expansion pressure.",

        "Bull Put Credit Spread":
            "Bullish credit-spread fit adjusted from "
            "live SPX directional evidence.",

        "Bear Call Credit Spread":
            "Bearish credit-spread fit adjusted from "
            "live SPX directional evidence.",

        "Debit Call Spread":
            "Bullish directional fit increases as "
            "upside displacement and expansion rise.",

        "Debit Put Spread":
            "Bearish directional fit increases as "
            "downside displacement and expansion rise.",

        "Butterfly":
            "Pinning and contained-range fit adjusted "
            "from live displacement and range behavior.",
    }

    strategies = []

    for name in names:
        item = build_strategy(
            name,
            int(
                round(
                    scores[name]
                )
            ),
            reasons[name],
            factors[name],
        )

        item.update(
            {
                "model_version":
                    "V2_OBSERVATION",
                "observation_only":
                    True,
                "direction_state":
                    direction_state,
                "signed_displacement_pct":
                    round(
                        signed_displacement_pct,
                        1,
                    ),
                "pressure_ratio":
                    (
                        round(
                            pressure_ratio,
                            2,
                        )
                        if pressure_ratio
                        is not None
                        else None
                    ),
                "range_band_consumed_pct":
                    (
                        round(
                            range_used,
                            1,
                        )
                        if range_used
                        is not None
                        else None
                    ),
                "execution_supported":
                    name
                    in {
                        "Iron Condor",
                        "Bull Put Credit Spread",
                        "Bear Call Credit Spread",
                    },
            }
        )

        strategies.append(item)

    strategies.sort(
        key=lambda s: (
            s["score"],
            strategy_priority.get(
                s["name"],
                0,
            ),
        ),
        reverse=True,
    )

    return strategies
