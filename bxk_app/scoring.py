from bxk_app.models import MarketDecision
from bxk_app.schwab_client import get_market_snapshot


def score_market() -> MarketDecision:
    market = get_market_snapshot()

    score = 0
    reasons = []

    # VIX
    if 12 <= market.vix <= 20:
        score += 1
        vix_state = "IDEAL"
        reasons.append("VIX ideal")
    else:
        vix_state = "OUTSIDE RANGE"
        reasons.append("VIX outside range")

    # Expected Move
    if market.expected_move >= 50:
        score += 1
        expected_move_state = "HEALTHY"
        reasons.append("Expected move healthy")
    else:
        expected_move_state = "LOW"
        reasons.append("Expected move too small")

    # IV Rank
    if market.iv_rank >= 20:
        score += 1
        iv_rank_state = "GOOD"
        reasons.append("IV rank good")
    else:
        iv_rank_state = "LOW"
        reasons.append("IV rank low")

    # Placeholder trend until live VWAP/EMA logic
    trend = "MIXED"

    confidence = int(score / 3 * 100)

    if score == 3:
        market_regime = "TRADE"
        recommendation = "Trade allowed"
    elif score == 2:
        market_regime = "CAUTION"
        recommendation = "Small size only"
    else:
        market_regime = "WAIT"
        recommendation = "No trade"

    return MarketDecision(
        market_regime=market_regime,
        confidence=confidence,
        score=score,
        trend=trend,
        vix_state=vix_state,
        expected_move_state=expected_move_state,
        iv_rank_state=iv_rank_state,
        recommendation=recommendation,
        reasons=reasons,
    )