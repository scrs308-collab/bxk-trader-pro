from bxk_app.qqq_decision import (
    evaluate_qqq_condor_decision,
)


def score(value):
    return {
        "available": True,
        "score": value,
    }


def priced_candidate():
    return {
        "available": True,
        "pricing_ready": True,
    }


def test_hostile_qqq_stability_denies_trade():
    result = evaluate_qqq_condor_decision(
        stability_score_detail=score(0.1),
        candidate_result=priced_candidate(),
    )

    assert result["strategy_status"] == "DENIED"
    assert result["market_permission"] == "WAIT"
    assert result["final_decision"] == "NO TRADE"

    assert (
        result["reason_code"]
        == "STABILITY_DENIED"
    )

    assert result["execution_enabled"] is False


def test_middle_qqq_stability_is_caution():
    result = evaluate_qqq_condor_decision(
        stability_score_detail=score(60),
        candidate_result=priced_candidate(),
    )

    assert result["strategy_status"] == "CAUTION"
    assert result["market_permission"] == "CAUTION"
    assert result["final_decision"] == "NO TRADE"

    assert (
        result["reason_code"]
        == "STABILITY_CAUTION"
    )


def test_strong_stability_still_does_not_authorize_trade():
    result = evaluate_qqq_condor_decision(
        stability_score_detail=score(82),
        candidate_result=priced_candidate(),
    )

    assert result["strategy_status"] == "APPROVED"
    assert result["market_permission"] == "TRADE"

    assert (
        result["candidate_quality_pending"]
        is True
    )

    assert result["trade_quality_score"] is None
    assert result["trade_quality_required"] is True

    assert result["final_decision"] == "NO TRADE"
    assert result["signal_ready"] is False
    assert result["execution_enabled"] is False

    assert (
        result["reason_code"]
        == "QQQ_EXECUTION_NOT_AUTHORIZED"
    )


def test_unavailable_stability_fails_closed():
    result = evaluate_qqq_condor_decision(
        stability_score_detail={
            "available": False,
            "score": None,
        },
        candidate_result=priced_candidate(),
    )

    assert result["market_permission"] == "WAIT"
    assert result["strategy_status"] == "DENIED"
    assert result["final_decision"] == "NO TRADE"

    assert (
        result["reason_code"]
        == "STABILITY_UNAVAILABLE"
    )
