"""
BXK Trader Pro

Strategy Engine

Purpose:
Selects the preferred strategy based on Market DNA and Trade Quality.
"""


class StrategyEngine:

    def run(self, market_snapshot, market_dna, trade_quality):

        dna = market_dna.get("classification", "Unknown")
        score = trade_quality.get("score", 0)

        if score < 70:
            strategy = "None"
            reason = "Trade quality too low"

        elif dna in ["Balanced Auction", "Calm Auction"]:
            strategy = "Iron Condor"
            reason = "Market favors premium selling"

        elif dna in ["Volatile Auction", "High Stress"]:
            strategy = "Directional"
            reason = "Volatility elevated"

        else:
            strategy = "Monitor"
            reason = "Market DNA unclear"

        return {
            "strategy": strategy,
            "reason": reason,
        }