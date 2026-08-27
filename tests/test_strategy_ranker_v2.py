from bxk_app.strategy_ranker import (
    rank_strategies,
    rank_strategies_v2,
)


def _by_name(results):
    return {
        item["name"]: item
        for item in results
    }


def _stability(
    *,
    price,
    session_open=7800.0,
    implied_move=100.0,
    pressure_ratio=1.0,
    range_used=40.0,
):
    return {
        "available": True,
        "signal_ready": True,
        "spx_price": price,
        "session_open": session_open,
        "implied_move": implied_move,
        "range_band_consumed_pct":
            range_used,
        "range_expansion_pressure": {
            "available": True,
            "pressure_ratio":
                pressure_ratio,
        },
    }


def test_v2_bullish_market_separates_opposing_spreads():
    results = _by_name(
        rank_strategies_v2(
            90,
            "IDEAL",
            current_price=7830,
            condor_stability=_stability(
                price=7830,
            ),
        )
    )

    assert (
        results[
            "Bull Put Credit Spread"
        ]["score"]
        >
        results[
            "Bear Call Credit Spread"
        ]["score"]
    )

    assert (
        results[
            "Debit Call Spread"
        ]["score"]
        >
        results[
            "Debit Put Spread"
        ]["score"]
    )

    assert (
        results[
            "Bull Put Credit Spread"
        ]["direction_state"]
        == "BULLISH"
    )


def test_v2_bearish_market_separates_opposing_spreads():
    results = _by_name(
        rank_strategies_v2(
            90,
            "IDEAL",
            current_price=7770,
            condor_stability=_stability(
                price=7770,
            ),
        )
    )

    assert (
        results[
            "Bear Call Credit Spread"
        ]["score"]
        >
        results[
            "Bull Put Credit Spread"
        ]["score"]
    )

    assert (
        results[
            "Debit Put Spread"
        ]["score"]
        >
        results[
            "Debit Call Spread"
        ]["score"]
    )


def test_v2_neutral_contained_market_favors_condor():
    results = rank_strategies_v2(
        90,
        "IDEAL",
        current_price=7805,
        condor_stability=_stability(
            price=7805,
            pressure_ratio=0.70,
            range_used=20.0,
        ),
    )

    assert (
        results[0]["name"]
        == "Iron Condor"
    )

    assert (
        results[0]["direction_state"]
        == "NEUTRAL"
    )


def test_v2_strong_bullish_expansion_can_favor_debit_call():
    results = _by_name(
        rank_strategies_v2(
            90,
            "IDEAL",
            current_price=7860,
            condor_stability=_stability(
                price=7860,
                pressure_ratio=1.70,
                range_used=70.0,
            ),
        )
    )

    assert (
        results[
            "Debit Call Spread"
        ]["score"]
        >
        results[
            "Iron Condor"
        ]["score"]
    )

    assert (
        results[
            "Debit Call Spread"
        ]["score"]
        >
        results[
            "Debit Put Spread"
        ]["score"]
    )


def test_v2_marks_dashboard_model_observation_only():
    results = rank_strategies_v2(
        90,
        "IDEAL",
        current_price=7830,
        condor_stability=_stability(
            price=7830,
        ),
    )

    assert all(
        item["observation_only"]
        is True
        for item in results
    )

    assert all(
        item["model_version"]
        == "V2_OBSERVATION"
        for item in results
    )


def test_v2_falls_back_when_live_evidence_unavailable():
    results = rank_strategies_v2(
        90,
        "IDEAL",
        current_price=None,
        condor_stability={
            "available": False,
            "signal_ready": False,
        },
    )

    assert all(
        item["model_version"]
        == "V1_FALLBACK"
        for item in results
    )


def test_legacy_ranker_remains_available_for_scanner():
    results = _by_name(
        rank_strategies(
            90,
            "MIXED",
            "IDEAL",
        )
    )

    assert (
        results[
            "Bull Put Credit Spread"
        ]["score"]
        ==
        results[
            "Bear Call Credit Spread"
        ]["score"]
    )
