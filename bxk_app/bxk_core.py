"""
BXK Trader Pro
BXK Core

Central Orchestrator
"""

from datetime import datetime

from bxk_app.market_intelligence_engine import MarketIntelligenceEngine
from bxk_app.trade_quality_engine import TradeQualityEngine
from bxk_app.market_dna_engine import MarketDNAEngine
from bxk_app.action_engine import ActionEngine


class BXKCore:

    def __init__(self):

        self.market = MarketIntelligenceEngine()

        self.trade_quality = TradeQualityEngine()

        self.market_dna = MarketDNAEngine()

        self.action = ActionEngine()

    def evaluate(self):

        market = self.market.evaluate()

        quality = self.trade_quality.evaluate(market)

        dna = self.market_dna.evaluate(market)

        action = self.action.evaluate(quality)

        return {

            "app": "BXK Trader Pro",

            "version": "V4",

            "production": "V7.1.0",

            "timestamp": datetime.now().isoformat(),

            "market": market,

            "trade_quality": quality,

            "market_dna": dna,

            "action": action,

        }


def get_bxk_core():

    return BXKCore().evaluate()