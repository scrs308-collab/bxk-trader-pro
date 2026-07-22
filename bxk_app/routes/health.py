import os

from fastapi import APIRouter


router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get("/api/health")
def health():
    return {
        "status": "OK",
        "app": "BXK Trader Pro",
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