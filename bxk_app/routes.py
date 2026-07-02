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
        "reasons": market_score.reasons,
    }