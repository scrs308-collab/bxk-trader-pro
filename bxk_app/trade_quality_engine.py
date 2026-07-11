class TradeQualityEngine:

    def run(self, market):
        score = 85

        strengths = []
        weaknesses = []

        trend = market.get("trend", "UNKNOWN")
        vix_state = market.get("vix_state", "")
        expected_move_state = market.get("expected_move_state", "")
        iv_rank_state = market.get("iv_rank_state", "")

        if trend == "UNKNOWN":
            score = 50
            weaknesses.append(
                {
                    "reason": "Trend is unknown",
                    "impact": -35,
                }
            )
        else:
            strengths.append(
                {
                    "reason": f"Trend identified as {trend}",
                    "impact": 0,
                }
            )

        if vix_state == "IDEAL":
            score += 5
            strengths.append(
                {
                    "reason": "VIX is in the ideal range",
                    "impact": 5,
                }
            )
        elif vix_state in ("HIGH", "OUTSIDE RANGE"):
            score -= 10
            weaknesses.append(
                {
                    "reason": f"VIX state is {vix_state}",
                    "impact": -10,
                }
            )

        if expected_move_state == "HEALTHY":
            score += 5
            strengths.append(
                {
                    "reason": "Expected move is healthy",
                    "impact": 5,
                }
            )
        elif expected_move_state == "LOW":
            score -= 10
            weaknesses.append(
                {
                    "reason": "Expected move is too low",
                    "impact": -10,
                }
            )

        if iv_rank_state == "GOOD":
            score += 5
            strengths.append(
                {
                    "reason": "IV rank supports premium selling",
                    "impact": 5,
                }
            )
        elif iv_rank_state == "LOW":
            score -= 10
            weaknesses.append(
                {
                    "reason": "IV rank is too low",
                    "impact": -10,
                }
            )

        score = max(0, min(100, round(score)))

        grade = self.grade(score)
        confidence = self.confidence(score)

        return {
            "score": score,
            "grade": grade,
            "confidence": confidence,
            "quality_label": f"{grade} {self.label(score)}",
            "strengths": strengths,
            "weaknesses": weaknesses,
        }

    def grade(self, score):
        if score >= 95:
            return "A+"

        if score >= 90:
            return "A"

        if score >= 85:
            return "A-"

        if score >= 80:
            return "B+"

        if score >= 75:
            return "B"

        if score >= 70:
            return "C"

        if score >= 60:
            return "D"

        return "F"

    def label(self, score):
        if score >= 95:
            return "Elite"

        if score >= 90:
            return "Excellent"

        if score >= 85:
            return "Strong"

        if score >= 80:
            return "Good"

        if score >= 75:
            return "Acceptable"

        if score >= 70:
            return "Fair"

        if score >= 60:
            return "Weak"

        return "Poor"

    def confidence(self, score):
        if score >= 90:
            return "High"

        if score >= 80:
            return "Medium"

        return "Low"