class TradeQualityEngine:

    def evaluate(self, market):

        score = 85

        if market["trend"] == "UNKNOWN":
            score = 50

        return {

            "score": score,

            "grade": self.grade(score),

            "confidence": self.confidence(score),

        }

    def grade(self, score):

        if score >= 95:
            return "A+"

        if score >= 90:
            return "A"

        if score >= 85:
            return "B+"

        if score >= 80:
            return "B"

        return "C"

    def confidence(self, score):

        if score >= 90:
            return "High"

        if score >= 80:
            return "Medium"

        return "Low"