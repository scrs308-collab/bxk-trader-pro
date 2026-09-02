from bxk_app.overnight_carry_risk import (
    calculate_overnight_carry_risk,
)


def test_green_when_cushion_exceeds_one_day_move():
    result = calculate_overnight_carry_risk(
        spx_close=7650,
        short_put=7550,
        short_call=7750,
        expected_move=80,
        expected_move_source="VIX1D",
        dte=1,
    )

    assert result["available"] is True
    assert result["state"] == "GREEN"
    assert (
        result["decision"]
        == "CARRY_WITH_MONITORING"
    )
    assert (
        result["cushion_to_1d_em_ratio"]
        == 1.25
    )


def test_yellow_below_one_day_move():
    result = calculate_overnight_carry_risk(
        spx_close=7650,
        short_put=7580,
        short_call=7750,
        expected_move=80,
        expected_move_source="VIX",
        dte=1,
    )

    assert result["state"] == "YELLOW"
    assert result["decision"] == "CAUTION"
    assert result["threatened_side"] == "PUT"


def test_orange_below_three_quarters_move():
    result = calculate_overnight_carry_risk(
        spx_close=7650,
        short_put=7600,
        short_call=7750,
        expected_move=80,
        dte=1,
    )

    assert result["state"] == "ORANGE"
    assert result["decision"] == "HIGH_RISK"
    assert result["short_cushion"] == 50


def test_red_below_half_expected_move():
    result = calculate_overnight_carry_risk(
        spx_close=7630,
        short_put=7600,
        short_call=7700,
        expected_move=80,
        dte=1,
    )

    assert result["state"] == "RED"
    assert result["decision"] == "DO_NOT_CARRY"
    assert (
        result["recommendation"]
        == "CLOSE_BEFORE_BELL"
    )


def test_breached_short_is_critical():
    result = calculate_overnight_carry_risk(
        spx_close=7595,
        short_put=7600,
        short_call=7700,
        expected_move=80,
        dte=1,
    )

    assert result["state"] == "CRITICAL"
    assert result["decision"] == "DO_NOT_CARRY"
    assert (
        result["reason_code"]
        == "SHORT_STRIKE_BREACHED"
    )


def test_zero_dte_is_not_overnight_candidate():
    result = calculate_overnight_carry_risk(
        spx_close=7650,
        short_put=7600,
        short_call=7700,
        expected_move=80,
        dte=0,
    )

    assert result["available"] is False
    assert (
        result["decision"]
        == "NOT_APPLICABLE"
    )


def test_missing_expected_move_fails_closed():
    result = calculate_overnight_carry_risk(
        spx_close=7650,
        short_put=7600,
        short_call=7700,
        expected_move=0,
        dte=1,
    )

    assert result["available"] is False
    assert result["decision"] == "UNAVAILABLE"
