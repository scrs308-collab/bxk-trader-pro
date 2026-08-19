import pytest
from fastapi import HTTPException

from bxk_app.routes import market as route


def test_underlying_discovery_route_registered():
    paths = {
        item.path
        for item in route.router.routes
    }

    assert (
        "/api/underlying-discovery"
        in paths
    )


def test_underlying_discovery_uses_service(
    monkeypatch,
):
    monkeypatch.setattr(
        route,
        "discover_underlying",
        lambda symbol: {
            "symbol": symbol,
            "quote_available": True,
            "options_available": True,
            "analysis_enabled": True,
            "execution_enabled": False,
            "reason_code":
                "DISCOVERY_READY",
        },
    )

    result = (
        route.underlying_discovery(
            "SPY"
        )
    )

    assert result["symbol"] == "SPY"

    assert (
        result["analysis_enabled"]
        is True
    )

    assert (
        result["execution_enabled"]
        is False
    )


def test_underlying_discovery_bad_symbol_is_400(
    monkeypatch,
):
    def fail(symbol):
        raise ValueError(
            "Underlying symbol is required."
        )

    monkeypatch.setattr(
        route,
        "discover_underlying",
        fail,
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        route.underlying_discovery(
            "BAD"
        )

    assert exc.value.status_code == 400

    assert (
        exc.value.detail
        == "Underlying symbol is required."
    )
