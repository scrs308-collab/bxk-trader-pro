

def analyze_trade(trade: dict):
    """
    Weighted trade scoring engine.
    Maximum score = 100
    """

    score = 0
    reasons = []
    credit = float(trade.get("credit", 0))
    pop = float(trade.get("pop", 0))

    touch_raw = trade.get("probability_of_touch")
    touch = float(touch_raw) if touch_raw is not None else None

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
        score += 20

    elif pop >= 85:
        score += 18

    elif pop >= 80:
        score += 16

    elif pop >= 75:
        score += 12

    elif pop >= 70:
        score += 8

    # ---------------------------
    # Probability of Touch
    # ---------------------------

    if touch is not None:

        if touch <= 25:
            score += 15
            reasons.append("Very low touch probability")

        elif touch <= 35:
            score += 12
            reasons.append("Low touch probability")

        elif touch <= 45:
            score += 8
            reasons.append("Moderate touch probability")

        else:
            score += 4
            reasons.append("High touch probability")

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
        grade = "A+"
        rating = "Elite"

    elif score >= 90:
        grade = "A"
        rating = "Excellent"

    elif score >= 85:
        grade = "A-"
        rating = "Strong"

    elif score >= 80:
        grade = "B+"
        rating = "Good"

    elif score >= 75:
        grade = "B"
        rating = "Acceptable"

    elif score >= 70:
        grade = "C"
        rating = "Fair"

    elif score >= 60:
        grade = "D"
        rating = "Weak"

    else:
        grade = "F"
        rating = "Poor"

    return {
    "trade_score": score,
    "grade": grade,
    "rating": rating,
    "quality_label": f"{grade} {rating}",
    "reasons": reasons,
}
    