import pytest

from bxk_app.services.position_service import (
    _attach_provisional_carry_risk,
)


def test_live_position_carry_is_orange():
    summaries = [
        {
            "strategy": "SPX Iron Condor",
            "sell_put": 7610.0,
            "buy_put": 7585.0,
            "sell_call": 7725.0,
            "buy_call": 7750.0,
            "dte": 1,
        }
    ]

    snapshot = {
        "expected_move": 73.49,
        "vix1d": 16.0,
        "vix": 17.0,
        "timestamp": (
            "2026-09-02T14:55:00-04:00"
        ),
    }

    result = (
        _attach_provisional_carry_risk(
            summaries,
            snapshot=snapshot,
            spx_price=7664.61,
        )
    )

    carry = result[0]["carry_risk"]

    assert carry["available"] is True
    assert carry["state"] == "ORANGE"
    assert carry["decision"] == "HIGH_RISK"

    assert (
        carry["threatened_side"]
        == "PUT"
    )

    assert carry[
        "short_cushion"
    ] == pytest.approx(
        54.61,
        abs=0.01,
    )

    assert carry[
        "cushion_to_1d_em_ratio"
    ] == pytest.approx(
        54.61 / 73.49,
        abs=0.001,
    )

    assert (
        carry["expected_move_source"]
        == "VIX1D"
    )

    assert (
        carry["evaluation_phase"]
        == "PROVISIONAL"
    )
