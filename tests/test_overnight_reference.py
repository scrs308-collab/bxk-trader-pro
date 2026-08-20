from bxk_app.overnight_reference import (
    calculate_overnight_spx_reference,
)
from bxk_app.overnight_risk import (
    calculate_overnight_risk,
)


REAL_ES_QUOTE = {
    "ask": "7696.25",
    "bid": "7696.0",
    "last": "7696.25",
    "last-mkt": "7696.25",
    "mark": "7696.25",
    "mid": "7696.125",
    "open": "7733.0",
    "prev-close": "7729.0",
    "symbol": "/ESU6",
    "updated-at":
        "2026-08-20T13:11:45.010Z",
}


def test_real_es_quote_produces_reference():
    result = (
        calculate_overnight_spx_reference(
            prior_spx_close=7707.98,
            es_quote=REAL_ES_QUOTE,
        )
    )

    assert result["available"] is True
    assert result["reference_source"] == "ES_PROXY"
    assert result["symbol"] == "/ESU6"

    assert result["price_source"] == "MID"
    assert result["es_price"] == 7696.125

    assert result["es_anchor_price"] == 7729.0
    assert result["es_move"] == -32.875

    assert result["estimated_spx"] == 7675.1


def test_prev_close_anchor_is_explicit_fallback():
    result = (
        calculate_overnight_spx_reference(
            prior_spx_close=7707.98,
            es_quote=REAL_ES_QUOTE,
        )
    )

    assert (
        result["es_anchor_source"]
        == "ES_PREV_CLOSE"
    )

    assert (
        result["calibration_quality"]
        == "FALLBACK"
    )

    assert (
        result["reason_code"]
        == "ES_PREV_CLOSE_PROXY_AVAILABLE"
    )


def test_supplied_close_snapshot_is_preferred():
    result = (
        calculate_overnight_spx_reference(
            prior_spx_close=7707.98,
            es_quote=REAL_ES_QUOTE,
            es_anchor_price=7728.50,
        )
    )

    assert (
        result["es_anchor_source"]
        == "CLOSE_SNAPSHOT"
    )

    assert (
        result["calibration_quality"]
        == "PREFERRED"
    )

    assert (
        result["reason_code"]
        == "ES_CLOSE_ANCHOR_PROXY_AVAILABLE"
    )


def test_missing_es_quote_fails_closed():
    result = (
        calculate_overnight_spx_reference(
            prior_spx_close=7707.98,
            es_quote=None,
        )
    )

    assert result["available"] is False
    assert result["state"] == "UNAVAILABLE"


def test_real_quote_drives_today_trade_critical():
    reference = (
        calculate_overnight_spx_reference(
            prior_spx_close=7707.98,
            es_quote=REAL_ES_QUOTE,
        )
    )

    risk = calculate_overnight_risk(
        reference_price=(
            reference["estimated_spx"]
        ),
        prior_close=7707.98,
        long_put=7670,
        short_put=7695,
        short_call=7790,
        long_call=7815,
        quantity=4,
        opening_credit=4.50,
        reference_source="ES_PROXY",
        market_status="GTH",
        dte=0,
    )

    assert risk["state"] == "CRITICAL"

    assert (
        risk["reason_code"]
        == "SHORT_STRIKE_BREACHED"
    )

    assert (
        risk["threatened_side"]
        == "PUT"
    )

    assert (
        risk["short_strike_breached"]
        is True
    )

    assert (
        risk["long_strike_breached"]
        is False
    )
