import pytest
from fastapi import HTTPException

from bxk_app.routes import market as route


def test_underlying_analysis_route_registered():
    paths = {
        item.path
        for item in route.router.routes
    }

    assert (
        "/api/underlying-analysis"
        in paths
    )


def test_underlying_analysis_calls_service(
    monkeypatch,
):
    captured = {}

    def fake_analysis(
        symbol,
        *,
        days_to_expiration=None,
        wing_width=None,
    ):
        captured["symbol"] = symbol
        captured["dte"] = days_to_expiration
        captured["wing_width"] = wing_width

        return {
            "symbol": symbol,
            "analysis_ready": True,
            "execution_enabled": False,
        }

    monkeypatch.setattr(
        route,
        "analyze_underlying",
        fake_analysis,
    )

    result = route.underlying_analysis(
        "SPY",
        dte=0,
        wing_width=5,
    )

    assert captured == {
        "symbol": "SPY",
        "dte": 0,
        "wing_width": 5,
    }

    assert result["analysis_ready"] is True
    assert result["execution_enabled"] is False


def test_underlying_analysis_value_error_is_400(
    monkeypatch,
):
    def fail(*args, **kwargs):
        raise ValueError(
            "Invalid underlying."
        )

    monkeypatch.setattr(
        route,
        "analyze_underlying",
        fail,
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        route.underlying_analysis(
            "BAD",
            dte=0,
            wing_width=5,
        )

    assert exc.value.status_code == 400

    assert (
        exc.value.detail
        == "Invalid underlying."
    )
