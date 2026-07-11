from pydantic import BaseModel, Field
from typing import List


class MarketDecision(BaseModel):
    market_regime: str
    confidence: int
    score: int
    trend: str
    vix_state: str
    expected_move_state: str
    iv_rank_state: str
    recommendation: str
    reasons: List[str]
    grade: str | None = None
    quality_label: str | None = None
    strengths: list[dict] = Field(default_factory=list)
    weaknesses: list[dict] = Field(default_factory=list)
class TradeRecommendation(BaseModel):
    trade: str
    confidence: int
    score: int
    reasons: List[str]


class MarketSnapshot(BaseModel):
    symbol: str
    price: float
    vix: float
    atr: float
    iv_rank: float
    expected_move: float