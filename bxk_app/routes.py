from fastapi import APIRouter
from fastapi.responses import FileResponse

from bxk_app.scoring import score_market
from bxk_app.strategy_ranker import rank_strategies
router = APIRouter()


@router.get("/health")
def health():
    return {"status": "OK"}


@router.get("/recommend")
def recommend():
    market = score_market()
    strategies = rank_strategies(
    market.score * 30,
    market.trend,
    market.vix_state
)

    return {
        "trade": market.market_regime,
        "confidence": market.confidence,
        "score": market.score,
        "trend": market.trend,
        "vix_state": market.vix_state,
        "expected_move_state": market.expected_move_state,
        "iv_rank_state": market.iv_rank_state,
        "recommendation": market.recommendation,
        "reasons": market.reasons,
        "strategies": strategies,
    }


@router.get("/")
@router.get("/dashboard")
def dashboard():
    return FileResponse("static/index.html")