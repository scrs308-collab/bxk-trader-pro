from bxk_app.market_engine import market_engine
from datetime import datetime

from fastapi import APIRouter

from bxk_app.market_data import market_data
from bxk_app.scoring import score_market
from bxk_app.strategy_ranker import rank_strategies
from bxk_app.tastytrade_client import tastytrade_client


router = APIRouter()

@router.get("/api/test-env")
def test_env():
    import os

    return {
        "client_id_loaded": bool(TASTYTRADE_CLIENT_ID),
        "client_secret_loaded": bool(TASTYTRADE_CLIENT_SECRET),
        "refresh_token_loaded": bool(TASTYTRADE_REFRESH_TOKEN),
        "tt_secret_loaded": bool(os.getenv("TT_SECRET")),
        "tt_refresh_token_loaded": bool(os.getenv("TT_REFRESH_TOKEN")),
    }

@router.get("/health")
def health():
    return {"status": "OK"}


@router.get("/api/health")
def api_health():
    return {"status": "OK"}


@router.get("/recommend")
def recommend_short():
    return recommend()


@router.get("/api/recommend")
def recommend():
    market = score_market()

    strategies = rank_strategies(
        market.score * 30,
        market.trend,
        market.vix_state,
    )

    return {
        "app": "BXK Trader Pro",
        "version": "6.0",
        "status": "OK",
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


@router.get("/api/debug")
def debug():
    return {
        "app": "BXK Trader Pro",
        "version": "6.0",
        "status": "debug route active",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "market_engine": market_engine.get_status(),
        "market_snapshot": market_data.get_snapshot(),
    }
@router.get("/api/refresh-market")
def refresh_market():
    market_engine.refresh()

    return {
        "status": "market refresh complete",
        "market_engine": market_engine.get_status(),
        "market_snapshot": market_data.get_snapshot(),
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


@router.get("/api/live-market")
def live_market():
    return market_data.get_header()

@router.get("/api/test-tastytrade")
def test_tastytrade():
    success = tastytrade_client.connect()

    return {
        "connected": success,
        "status": tastytrade_client.get_status(),
    }