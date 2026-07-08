from bxk_app.models import MarketDecision
from bxk_app.market_data import market_data


def run_trade_quality() -> MarketDecision:
    try:
        snapshot = market_data.get_snapshot()
    except Exception as e:
        return MarketDecision(
            market_regime="WAIT",
            confidence=0,
            score=0,
            trend="UNKNOWN",
            vix_state="UNKNOWN",
            expected_move_state="UNKNOWN",
            iv_rank_state="UNKNOWN",
            recommendation=f"Market data unavailable: {str(e)}",
            reasons=["Unable to retrieve market snapshot"],
        )

    score = 0
    reasons = []

    vix = snapshot["vix"]
    expected_move = snapshot["expected_move"]
    iv_rank = snapshot["iv_rank"]

    if 12 <= vix <= 20:
        score += 1
        vix_state = "IDEAL"
        reasons.append("VIX ideal")
    else:
        vix_state = "OUTSIDE RANGE"
        reasons.append("VIX outside range")

    if expected_move >= 50:
        score += 1
        expected_move_state = "HEALTHY"
        reasons.append("Expected move healthy")
    else:
        expected_move_state = "LOW"
        reasons.append("Expected move too small")

    if iv_rank >= 20:
        score += 1
        iv_rank_state = "GOOD"
        reasons.append("IV rank good")
    else:
        iv_rank_state = "LOW"
        reasons.append("IV rank low")

    trend = "MIXED"
    score_percent = int((score / 3) * 100)
    confidence = score_percent
   

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
        score=score_percent,
        trend=trend,
        vix_state=vix_state,
        expected_move_state=expected_move_state,
        iv_rank_state=iv_rank_state,
        recommendation=recommendation,
        reasons=reasons,
    )