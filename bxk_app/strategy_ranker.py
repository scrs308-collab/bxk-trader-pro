from typing import List, Dict


def build_strategy(
    name: str,
    score: int,
    reason: str,
) -> Dict:

    return {
        "name": name,
        "score": max(
            0,
            min(score, 100),
        ),
        "confidence": (
            "High"
            if score >= 80
            else "Medium"
            if score >= 60
            else "Low"
        ),
        "reason": reason,
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

    if vix_state == "IDEAL":
        score += 10

    if trend == "MIXED":
        score += 10

    strategies.append(
        build_strategy(
            "Iron Condor",
            score,
            "Balanced market with healthy premium.",
        )
    )

    # ============================================
    # Bull Put Credit Spread
    # ============================================

    score = 45

    if trend == "BULL":
        score += 30

    if vix_state == "IDEAL":
        score += 10

    strategies.append(
        build_strategy(
            "Bull Put Credit Spread",
            score,
            "Bullish conditions favor selling put premium.",
        )
    )

    # ============================================
    # Bear Call Credit Spread
    # ============================================

    score = 45

    if trend == "BEAR":
        score += 30

    if vix_state == "IDEAL":
        score += 10

    strategies.append(
        build_strategy(
            "Bear Call Credit Spread",
            score,
            "Bearish conditions favor selling call premium.",
        )
    )

    # ============================================
    # Debit Call
    # ============================================

    score = 35

    if trend == "BULL":
        score += 35

    strategies.append(
        build_strategy(
            "Debit Call Spread",
            score,
            "Directional bullish strategy.",
        )
    )

    # ============================================
    # Debit Put
    # ============================================

    score = 35

    if trend == "BEAR":
        score += 35

    strategies.append(
        build_strategy(
            "Debit Put Spread",
            score,
            "Directional bearish strategy.",
        )
    )

    # ============================================
    # Butterfly
    # ============================================

    score = 50

    if trend == "MIXED":
        score += 20

    strategies.append(
        build_strategy(
            "Butterfly",
            score,
            "Best near price magnets and low movement.",
        )
    )
    strategy_priority = {
        "Iron Condor": 6,
        "Bull Put Credit Spread": 5,
        "Bear Call Credit Spread": 5,
        "Butterfly": 4,
        "Debit Call Spread": 3,
        "Debit Put Spread": 3,
    }

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
