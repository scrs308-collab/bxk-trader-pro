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
