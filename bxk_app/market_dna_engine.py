class MarketDNAEngine:

    def evaluate(self, market):

        trend = market["trend"]

        if trend == "BULLISH":
            dna = "Trending"

        elif trend == "BEARISH":
            dna = "Trending"

        elif trend == "RANGE":
            dna = "Balanced"

        else:
            dna = "Unknown"

        return {

            "classification": dna

        }