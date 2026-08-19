from bxk_app.underlying_decision import (
    evaluate_underlying_condor_decision,
)


def score(value):
    return {
        "available": True,
        "score": value,
    }


def priced():
    return {
        "available": True,
        "pricing_ready": True,
    }


def test_hostile_market_is_denied():
    result = evaluate_underlying_condor_decision(
        symbol="SPY",
        stability_score_detail=score(20),
        candidate_result=priced(),
    )

    assert result["strategy_status"] == "DENIED"
    assert result["market_permission"] == "WAIT"
    assert result["reason_code"] == "STABILITY_DENIED"
    assert result["final_decision"] == "NO TRADE"
    assert result["execution_enabled"] is False


def test_middle_score_is_caution():
    result = evaluate_underlying_condor_decision(
        symbol="IWM",
        stability_score_detail=score(60),
        candidate_result=priced(),
    )

    assert result["strategy_status"] == "CAUTION"
    assert result["market_permission"] == "CAUTION"
    assert result["reason_code"] == "STABILITY_CAUTION"


def test_strong_unverified_symbol_remains_blocked():
    result = evaluate_underlying_condor_decision(
        symbol="SPY",
        stability_score_detail=score(82),
        candidate_result=priced(),
        verified_profile=False,
    )

    assert result["strategy_status"] == "APPROVED"
    assert result["market_permission"] == "TRADE"
    assert result["candidate_quality_pending"] is True

    assert (
        result["reason_code"]
        == "UNVERIFIED_PROFILE_EXECUTION_BLOCKED"
    )

    assert result["final_decision"] == "NO TRADE"
    assert result["execution_enabled"] is False


def test_strong_verified_symbol_still_not_authorized():
    result = evaluate_underlying_condor_decision(
        symbol="QQQ",
        stability_score_detail=score(82),
        candidate_result=priced(),
        verified_profile=True,
    )

    assert result["market_permission"] == "TRADE"
    assert result["reason_code"] == "EXECUTION_NOT_AUTHORIZED"
    assert result["final_decision"] == "NO TRADE"
    assert result["signal_ready"] is False
    assert result["execution_enabled"] is False


def test_missing_stability_fails_closed():
    result = evaluate_underlying_condor_decision(
        symbol="XSP",
        stability_score_detail={
            "available": False,
            "score": None,
        },
        candidate_result=priced(),
    )

    assert result["market_permission"] == "WAIT"
    assert result["reason_code"] == "STABILITY_UNAVAILABLE"
    assert result["execution_enabled"] is False
