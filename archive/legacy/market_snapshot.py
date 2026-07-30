"""
BXK Trader Pro

Market Snapshot

Shared data model passed between all engines.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketSnapshot:

    timestamp: datetime

    spx: float | None

    vix: float | None

    vix1d: float | None

    expected_move: float | None

    trend: str

    volatility: str

    market_regime: str