import os

from fastapi import APIRouter

from bxk_app.services.market_heartbeat_service import (
    get_market_heartbeat_status,
)


router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    """
    Lightweight process liveness endpoint.

    This intentionally remains independent of market-data
    health so a temporary broker outage does not cause the
    hosting platform to restart a healthy BXK process.
    """
    return {
        "status": "OK",
        "app": "BXK Trader Pro",
    }


@router.get("/api/health")
def api_health():
    """
    Detailed authenticated runtime health.
    """
    return {
        "status": "OK",
        "app": "BXK Trader Pro",
        "market_heartbeat":
            get_market_heartbeat_status(),
    }


@router.get("/api/test-env")
def test_environment():
    """
    Confirm that required environment variables are loaded.

    This endpoint reports only whether values exist.
    It never exposes credentials.
    """

    return {
        "client_id_loaded": bool(
            os.getenv("TASTYTRADE_CLIENT_ID")
        ),
        "client_secret_loaded": bool(
            os.getenv("TASTYTRADE_CLIENT_SECRET")
        ),
        "refresh_token_loaded": bool(
            os.getenv("TASTYTRADE_REFRESH_TOKEN")
        ),
        "tt_secret_loaded": bool(
            os.getenv("TT_SECRET")
        ),
        "tt_refresh_token_loaded": bool(
            os.getenv("TT_REFRESH_TOKEN")
        ),
    }