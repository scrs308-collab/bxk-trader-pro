def analyze_trade(trade: dict):
    """
    Weighted trade scoring engine.
    Maximum score = 100
    """

    score = 0
    reasons = []

    credit = float(trade.get("credit", 0))
    pop = float(trade.get("pop", 0))
    risk_reward = float(trade.get("risk_reward", 99))
    wing = int(trade.get("wing_width", 25))

    market_score = float(trade.get("market_score", 0))
    market_regime = trade.get("market_regime", "WAIT")
    trend = trade.get("trend", "UNKNOWN")
    vix_state = trade.get("vix_state", "")
    expected_move_state = trade.get("expected_move_state", "")

    # ---------------------------
    # Market Regime (25)
    # ---------------------------

    if market_regime == "TRADE":
        score += 25
        reasons.append("Market conditions support trading")
    else:
        reasons.append("Market regime is defensive")

    # ---------------------------
    # Market Quality (20)
    # ---------------------------

    score += min(market_score * 0.20, 20)

    if market_score >= 80:
        reasons.append("Overall market quality is excellent")

    # ---------------------------
    # VIX (15)
    # ---------------------------

    if vix_state == "IDEAL":
        score += 15
        reasons.append("VIX in optimal range")

    elif vix_state == "GOOD":
        score += 10
        reasons.append("VIX acceptable")

    elif vix_state == "HIGH":
        score += 5
        reasons.append("High volatility")

    # ---------------------------
    # Expected Move (10)
    # ---------------------------

    if expected_move_state == "HEALTHY":
        score += 10
        reasons.append("Expected move favorable")

    elif expected_move_state == "GOOD":
        score += 7

    elif expected_move_state == "LOW":
        score += 3

    # ---------------------------
    # Credit (10)
    # ---------------------------

    if credit >= 2.50:
        score += 10
        reasons.append("Premium exceeds target")

    elif credit >= 2.00:
        score += 8
        reasons.append("Premium acceptable")

    elif credit >= 1.50:
        score += 5

    # ---------------------------
    # Probability of Profit (10)
    # ---------------------------

    if pop >= 90:
        score += 10

    elif pop >= 85:
        score += 9

    elif pop >= 80:
        score += 8

    elif pop >= 75:
        score += 6

    reasons.append(f"Probability of profit {pop:.0f}%")

    # ---------------------------
    # Risk / Reward (5)
    # ---------------------------

    if risk_reward <= 8:
        score += 5

    elif risk_reward <= 10:
        score += 4

    elif risk_reward <= 12:
        score += 3

    reasons.append("Risk / reward acceptable")

    # ---------------------------
    # Wing Width (5)
    # ---------------------------

    if wing == 25:
        score += 5
        reasons.append("Preferred wing width")

    elif wing == 20:
        score += 4

    elif wing == 15:
        score += 3

    score = round(score)

    if score >= 95:
        rating = "A+ Elite"

    elif score >= 90:
        rating = "A Excellent"

    elif score >= 80:
        rating = "B Good"

    elif score >= 70:
        rating = "C Fair"

    else:
        rating = "D Poor"

    return {
        "trade_score": score,
        "rating": rating,
        "reasons": reasons,
    }