"""
BXK Trader Pro

Market DNA Engine

Purpose:
Determines the overall market personality from the live market snapshot.
"""


class MarketDNAEngine:

    def run(self, snapshot):

        dna = {

            "classification": self.classify(snapshot),

            "confidence": self.confidence(snapshot),

            "preferred_strategy": self.strategy(snapshot),

            "risk_level": self.risk(snapshot),

        }

        return dna

    def classify(self, snapshot):

        if snapshot.vix is None:
            return "Unknown"

        if snapshot.vix < 12:
            return "Calm Auction"

        if snapshot.vix < 18:
            return "Balanced Auction"

        if snapshot.vix < 25:
            return "Volatile Auction"

        return "High Stress"

    def confidence(self, snapshot):

        return 85

    def strategy(self, snapshot):

        if snapshot.vix is None:
            return "None"

        if snapshot.vix < 20:
            return "Iron Condor"

        return "Directional"

    def risk(self, snapshot):

        if snapshot.vix is None:
            return "Unknown"

        if snapshot.vix < 18:
            return "Low"

        if snapshot.vix < 25:
            return "Medium"

        return "High"