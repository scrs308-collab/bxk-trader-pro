from bxk_app.services import (
    overnight_risk_service,
)


ACTIVE_ES = {
    "symbol": "/ESU6",
    "streamer-symbol": "/ESU26:XCME",
    "expiration-date": "2026-09-18",
    "active": True,
    "active-month": True,
}


ES_QUOTE = {
    "ask": "7696.25",
    "bid": "7696.0",
    "mark": "7696.25",
    "last": "7696.25",
    "prev-close": "7729.0",
    "symbol": "/ESU6",
    "updated-at":
        "2026-08-20T13:11:45.010Z",
}


import pytest


@pytest.fixture(autouse=True)
def active_gth_session(monkeypatch):
    monkeypatch.setattr(
        overnight_risk_service,
        "get_spx_gth_session",
        lambda: {
            "active": True,
            "state": "GTH",
            "reason_code":
                "SPX_GTH_ACTIVE",
            "eastern_time":
                "2026-08-20T08:00:00-04:00",
        },
    )


TODAY_POSITION = {
    "strategy": "SPX Iron Condor",
    "underlying": "SPX",
    "quantity": 4,
    "expiration": "2026-08-20",
    "dte": 0,
    "buy_put": 7670,
    "sell_put": 7695,
    "sell_call": 7790,
    "buy_call": 7815,
    "opening_credit": 4.50,
    "max_risk": 8200.0,
}


def test_live_service_builds_critical_today_case(
    monkeypatch,
):
    monkeypatch.setattr(
        overnight_risk_service.broker,
        "get_active_future",
        lambda product_code: ACTIVE_ES,
    )

    monkeypatch.setattr(
        overnight_risk_service.broker,
        "get_future_quote",
        lambda symbol: ES_QUOTE,
    )

    monkeypatch.setattr(
        overnight_risk_service,
        "get_position_monitor",
        lambda: {
            "status": "OK",
            "positions": [
                TODAY_POSITION,
            ],
        },
    )

    result = (
        overnight_risk_service
        .get_live_overnight_risk(
            prior_spx_close=7707.98
        )
    )

    assert result["available"] is True
    assert result["state"] == "CRITICAL"
    assert (
        result["recommendation"]
        == "EXIT_REVIEW"
    )

    assert (
        result["reference"][
            "estimated_spx"
        ]
        == 7675.1
    )

    assert (
        result["positions"][0][
            "risk"
        ]["short_strike_breached"]
        is True
    )


def test_service_auto_uses_active_es_symbol(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        overnight_risk_service.broker,
        "get_active_future",
        lambda product_code: ACTIVE_ES,
    )

    def fake_quote(symbol):
        captured["symbol"] = symbol
        return ES_QUOTE

    monkeypatch.setattr(
        overnight_risk_service.broker,
        "get_future_quote",
        fake_quote,
    )

    monkeypatch.setattr(
        overnight_risk_service,
        "get_position_monitor",
        lambda: {
            "positions": [
                TODAY_POSITION,
            ]
        },
    )

    overnight_risk_service.get_live_overnight_risk(
        prior_spx_close=7707.98
    )

    assert captured["symbol"] == "/ESU6"


def test_service_reports_no_position(
    monkeypatch,
):
    monkeypatch.setattr(
        overnight_risk_service.broker,
        "get_active_future",
        lambda product_code: ACTIVE_ES,
    )

    monkeypatch.setattr(
        overnight_risk_service.broker,
        "get_future_quote",
        lambda symbol: ES_QUOTE,
    )

    monkeypatch.setattr(
        overnight_risk_service,
        "get_position_monitor",
        lambda: {
            "positions": [],
        },
    )

    result = (
        overnight_risk_service
        .get_live_overnight_risk(
            prior_spx_close=7707.98
        )
    )

    assert result["available"] is False
    assert result["state"] == "NO_POSITION"
    assert (
        result["reason_code"]
        == "NO_OPEN_SPX_CONDOR"
    )


def test_service_fails_closed_without_es_contract(
    monkeypatch,
):
    monkeypatch.setattr(
        overnight_risk_service.broker,
        "get_active_future",
        lambda product_code: None,
    )

    result = (
        overnight_risk_service
        .get_live_overnight_risk(
            prior_spx_close=7707.98
        )
    )

    assert result["available"] is False
    assert (
        result["reason_code"]
        == "ACTIVE_ES_CONTRACT_UNAVAILABLE"
    )
    assert (
        result["execution_authorized"]
        is False
    )


def test_service_fails_closed_without_prior_close():
    result = (
        overnight_risk_service
        .get_live_overnight_risk(
            prior_spx_close=None
        )
    )

    assert result["available"] is False
    assert (
        result["reason_code"]
        == "PRIOR_SPX_CLOSE_UNAVAILABLE"
    )


def test_service_fails_closed_outside_gth(
    monkeypatch,
):
    monkeypatch.setattr(
        overnight_risk_service,
        "get_spx_gth_session",
        lambda: {
            "active": False,
            "state": "INACTIVE",
            "reason_code":
                "SPX_GTH_INACTIVE",
            "eastern_time":
                "2026-08-20T12:00:00-04:00",
        },
    )

    result = (
        overnight_risk_service
        .get_live_overnight_risk(
            prior_spx_close=7707.98
        )
    )

    assert result["available"] is False
    assert result["state"] == "INACTIVE"
    assert (
        result["reason_code"]
        == "SPX_GTH_INACTIVE"
    )
    assert (
        result["execution_authorized"]
        is False
    )
