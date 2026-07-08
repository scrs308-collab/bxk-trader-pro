"""
BXK Trader Pro

BXK Core

Purpose:
Central orchestrator for the V4 engine pipeline.
"""

from datetime import datetime
from dataclasses import asdict, is_dataclass

from bxk_app.market_intelligence_engine import MarketIntelligenceEngine
from bxk_app.trade_quality_engine import TradeQualityEngine
from bxk_app.market_dna_engine import MarketDNAEngine
from bxk_app.action_engine import ActionEngine


class BXKCore:
    def __init__(self):
        self.version = "V4"
        self.production = "V7.1.0"

        self.market_engine = MarketIntelligenceEngine()
        self.trade_quality_engine = TradeQualityEngine()
        self.market_dna_engine = MarketDNAEngine()
        self.action_engine = ActionEngine()

    def run(self):
        market_snapshot = self.market_engine.run()
        market_dna = self.market_dna_engine.run(market_snapshot)
        trade_quality = self.trade_quality_engine.run(market_snapshot)
        action = self.action_engine.run(trade_quality)

        return {
            "app": "BXK Trader Pro",
            "version": self.version,
            "production": self.production,
            "timestamp": datetime.now().isoformat(),
            "market": self.to_dict(market_snapshot),
            "market_dna": self.to_dict(market_dna),
            "trade_quality": trade_quality,
            "action": action,
        }

    def to_dict(self, value):
        if is_dataclass(value):
            return asdict(value)

        return value


def get_bxk_core():
    return BXKCore().run()