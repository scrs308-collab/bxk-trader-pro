from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from bxk_app import trade_analyzer
from bxk_app.closing_flow_risk import (
    evaluate_closing_flow_risk,
)
from bxk_app.routes import order as order_route
from bxk_app.services.position_threat_service import (
    classify_position_threat,
)


ET = ZoneInfo("America/New_York")


def et(
    year,
    month,
    day,
    hour,
    minute,
):
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=ET,
    )


def test_guard_inactive_before_1540():
    risk = evaluate_closing_flow_risk(
        dte=0,
        strategy="SPX Iron Condor",
        now=et(
            2026,
            9,
            29,
            15,
            39,
        ),
    )

    assert risk["active"] is False
    assert risk["level"] == "NORMAL"
    assert risk["score_penalty"] == 0


def test_regular_day_1540_is_elevated_not_blocked():
    risk = evaluate_closing_flow_risk(
        dte=0,
        strategy="SPX Iron Condor",
        now=et(
            2026,
            9,
            29,
            15,
            40,
        ),
    )

    assert risk["active"] is True
    assert risk["level"] == "ELEVATED"
    assert risk["event"] == "LATE_SESSION"
    assert risk["score_penalty"] == 8
    assert risk["block_new_entry"] is False


def test_quarter_end_0dte_is_high_and_blocked():
    risk = evaluate_closing_flow_risk(
        dte=0,
        strategy="SPX Iron Condor",
        now=et(
            2026,
            9,
            30,
            15,
            40,
        ),
    )

    assert risk["active"] is True
    assert risk["level"] == "HIGH"
    assert risk["event"] == "QUARTER_END"
    assert risk["quarter_end_session"] is True
    assert risk["score_penalty"] == 20
    assert risk["block_new_entry"] is True


def test_month_end_0dte_is_high_and_blocked():
    risk = evaluate_closing_flow_risk(
        dte=0,
        strategy="SPX Iron Condor",
        now=et(
            2026,
            8,
            31,
            15,
            40,
        ),
    )

    assert risk["active"] is True
    assert risk["event"] == "MONTH_END"
    assert risk["quarter_end_session"] is False
    assert risk["block_new_entry"] is True


def test_1dte_is_not_penalized_at_quarter_end():
    risk = evaluate_closing_flow_risk(
        dte=1,
        strategy="SPX Iron Condor",
        now=et(
            2026,
            9,
            30,
            15,
            50,
        ),
    )

    assert risk["active"] is False
    assert risk["score_penalty"] == 0
    assert risk["block_new_entry"] is False


def test_position_monitor_tightens_after_1545():
    position = {
        "strategy": "SPX Iron Condor",
        "dte": 0,
        "spx_price": 7600,
        "sell_put": 7560,
        "sell_call": 7700,
        "put_distance": 40,
        "call_distance": 100,
    }

    before = classify_position_threat(
        position,
        now=et(
            2026,
            9,
            29,
            15,
            44,
        ),
    )
    after = classify_position_threat(
        position,
        now=et(
            2026,
            9,
            29,
            15,
            45,
        ),
    )

    assert before["state"] == "GREEN"
    assert after["state"] == "ORANGE"
    assert after[
        "closing_flow_risk"
    ][
        "tighten_position_monitor"
    ] is True
    assert after["red_threshold"] == 30.4
    assert after["orange_threshold"] == 45.6


def test_position_inside_point_four_percent_is_red():
    risk = classify_position_threat(
        {
            "strategy": "SPX Iron Condor",
            "dte": 0,
            "spx_price": 7600,
            "sell_put": 7575,
            "sell_call": 7700,
            "put_distance": 25,
            "call_distance": 100,
        },
        now=et(
            2026,
            9,
            29,
            15,
            46,
        ),
    )

    assert risk["state"] == "RED"



def test_analyzer_applies_penalty_and_hard_block(
    monkeypatch,
):
    monkeypatch.setattr(
        trade_analyzer,
        "evaluate_closing_flow_risk",
        lambda **kwargs: {
            "active": True,
            "level": "HIGH",
            "event": "QUARTER_END",
            "score_penalty": 20,
            "block_new_entry": True,
            "message": "Quarter-end test block.",
        },
    )

    result = trade_analyzer.analyze_trade(
        {
            "strategy": "SPX Iron Condor",
            "dte": 0,
            "credit": 3.25,
            "pop": 90,
            "probability_of_touch": 20,
            "risk_reward": 7,
            "wing_width": 25,
            "put_distance": 40,
            "call_distance": 40,
            "market_regime": "TRADE",
            "market_score": 90,
        }
    )

    assert result["trade_quality_score"] == 80
    assert result["final_decision"] == "NO TRADE"
    assert result["market_permission"] == "WAIT"
    assert result["closing_flow_risk"][
        "block_new_entry"
    ] is True
    assert any(
        item["reason"]
        == "Quarter-end test block."
        for item in result["weaknesses"]
    )


def test_order_builder_refuses_closing_flow_block(
    monkeypatch,
):
    trade = {
        "strategy": "SPX Iron Condor",
        "closing_flow_risk": {
            "block_new_entry": True,
        },
    }

    monkeypatch.setattr(
        order_route,
        "get_best_trade",
        lambda **kwargs: {
            "best_trade": trade,
        },
    )

    monkeypatch.setattr(
        order_route,
        "build_order",
        lambda *args, **kwargs: pytest.fail(
            "Blocked closing-flow trade "
            "must not reach order builder."
        ),
    )

    built_trade, order = (
        order_route._build_current_order(
            "iron_condor",
            0,
            25,
            1,
        )
    )

    assert built_trade is None
    assert order is None
