from bxk_app.overnight_risk import (
    calculate_overnight_risk,
)


TODAY = {
    "prior_close": 7707.98,
    "long_put": 7670,
    "short_put": 7695,
    "short_call": 7790,
    "long_call": 7815,
    "quantity": 4,
    "opening_credit": 4.50,
    "reference_source": "TEST",
    "market_status": "GTH",
    "dte": 0,
}


def risk_at(price):
    return calculate_overnight_risk(
        reference_price=price,
        **TODAY,
    )


def test_today_trade_max_risk_is_8200():
    result = risk_at(7707.98)

    assert result["available"] is True
    assert result["max_risk"] == 8200.0
    assert result["quantity"] == 4


def test_today_trade_identifies_put_as_threatened_side():
    result = risk_at(7707.98)

    assert result["threatened_side"] == "PUT"
    assert result["short_strike"] == 7695.0
    assert result["long_strike"] == 7670.0
    assert result["original_cushion"] == 12.98


def test_small_overnight_drop_enters_yellow():
    result = risk_at(7703.00)

    assert result["state"] == "YELLOW"
    assert result["recommendation"] == "WATCH"
    assert result["threatened_side"] == "PUT"
    assert result["short_strike_breached"] is False


def test_larger_drop_before_short_strike_enters_red():
    result = risk_at(7696.00)

    assert result["state"] == "RED"
    assert result["recommendation"] == "EXIT_REVIEW"
    assert result["short_strike_breached"] is False


def test_short_put_breach_is_critical():
    result = risk_at(7685.00)

    assert result["state"] == "CRITICAL"
    assert result["recommendation"] == "EXIT_REVIEW"
    assert result["reason_code"] == "SHORT_STRIKE_BREACHED"
    assert result["short_strike_breached"] is True
    assert result["long_strike_breached"] is False


def test_long_put_breach_is_critical():
    result = risk_at(7665.00)

    assert result["state"] == "CRITICAL"
    assert result["reason_code"] == "LONG_STRIKE_BREACHED"
    assert result["short_strike_breached"] is True
    assert result["long_strike_breached"] is True


def test_upside_move_identifies_call_side():
    result = risk_at(7775.00)

    assert result["threatened_side"] == "CALL"
    assert result["short_strike"] == 7790.0


def test_invalid_strike_order_fails_closed():
    result = calculate_overnight_risk(
        reference_price=7700,
        prior_close=7708,
        long_put=7700,
        short_put=7695,
        short_call=7790,
        long_call=7815,
        quantity=4,
        opening_credit=4.50,
    )

    assert result["available"] is False
    assert result["state"] == "UNAVAILABLE"
    assert result["reason_code"] == "INVALID_STRIKE_ORDER"
    assert result["execution_authorized"] is False


def test_missing_data_fails_closed():
    result = calculate_overnight_risk(
        reference_price=None,
        prior_close=7708,
        long_put=7670,
        short_put=7695,
        short_call=7790,
        long_call=7815,
        quantity=4,
        opening_credit=4.50,
    )

    assert result["available"] is False
    assert result["state"] == "UNAVAILABLE"
    assert result["execution_authorized"] is False


def test_module_is_explicitly_observation_only():
    result = risk_at(7685.00)

    assert result["observation_only"] is True
    assert result["execution_authorized"] is False
