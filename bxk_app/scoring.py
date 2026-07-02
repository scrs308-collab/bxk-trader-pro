from bxk_app.models import MarketDecision
from bxk_app.schwab_client import get_market_snapshot


def score_market() -> MarketDecision:

    market = get_market_snapshot()

    score = 0
    reasons = []

    # VIX
    if 12 <= market.vix <= 20:
        score += 1
        reasons.append("VIX Ideal")
    else:
        reasons.append("VIX Outside Range")

    # Expected Move
    if market.expected_move > 40:
        score += 1
        reasons.append("Healthy Expected Move")
    else:
        reasons.append("Expected Move Too Small")

    # IV Rank
    if market.iv_rank > 20:
        score += 1
        reasons.append("IV Rank Good")
    else:
        reasons.append("IV Rank Low")

    confidence = int(score / 3 * 100)

    if score == 3:
        trade = "TRADE"
    elif score == 2:
        trade = "CAUTION"
    else:
        trade = "WAIT"

    return MarketDecision(
        market_regime=trade,
        confidence=confidence,
        score=score,
        reasons=reasons,
    )