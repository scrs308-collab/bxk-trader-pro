from fastapi import APIRouter

from bxk_app.scoring import score_market

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "OK"
    }


@router.get("/recommend")
def recommend():
    market_score = score_market()

    return {
        "trade": market_score.market_regime,
        "confidence": market_score.confidence,
        "score": market_score.score,
        "trend": market_score.trend,
        "vix_state": market_score.vix_state,
        "expected_move_state": market_score.expected_move_state,
        "iv_rank_state": market_score.iv_rank_state,
        "recommendation": market_score.recommendation,
        "reasons": market_score.reasons,
    }