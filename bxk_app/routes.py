from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import FileResponse

from bxk_app.market_data import market_data
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
        market.vix_state,
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


@router.get("/api/market-brief")
def market_brief():
    market = score_market()

    if market.market_regime == "TRADE":
        summary = (
            f"Market conditions support trading. Trend is {market.trend}, "
            f"VIX is {market.vix_state}, expected move is {market.expected_move_state}, "
            f"and IV rank is {market.iv_rank_state}. Current setup favors premium-selling strategies."
        )
    else:
        summary = (
            f"Market conditions are not ideal. Trend is {market.trend}, "
            f"VIX is {market.vix_state}, expected move is {market.expected_move_state}, "
            f"and IV rank is {market.iv_rank_state}. Waiting is favored until conditions improve."
        )

    return {
        "title": "Market Narrative",
        "summary": summary,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    strategies = rank_strategies(
        market.score * 30,
        market.trend,
        market.vix_state,
    )

    return {
        "app": "BXK Trader Pro",
        "version": "5.1",
        "status": "LIVE",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
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


@router.get("/api/live-market")
def live_market():
    return market_data.get_header()


@router.get("/")
@router.get("/dashboard")
def dashboard():
    return FileResponse("static/index.html")