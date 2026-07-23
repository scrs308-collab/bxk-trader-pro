from bxk_app.live_option_engine import (
    calculate_iron_condor_credit,
)
from bxk_app.option_scanner import (
    generate_candidate_condors,
    normalize_candidate,
)
from bxk_app.scanner_engine import (
    find_best_iron_condor,
)
from bxk_app.scoring import run_trade_quality
from bxk_app.strategy_ranker import rank_strategies
from bxk_app.trade_builder import (
    build_best_bear_call,
    build_best_bull_put,
    build_best_trade,
)
from bxk_app.wing_optimizer import find_best_trade


def safe_market_value(
    market,
    field_name,
    default=None,
):
    """
    Safely read a value from either an object or dictionary.
    """

    if isinstance(market, dict):
        return market.get(
            field_name,
            default,
        )

    return getattr(
        market,
        field_name,
        default,
    )


def get_test_wing_optimizer():
    trade = find_best_trade(
        spx_price=7535.54,
        expected_move=62.5,
    )

    return {
        "trade": trade,
    }


def get_test_scanner_engine():
    trade = find_best_iron_condor(
        spx_price=7535.54,
        expected_move=62.5,
        wing_width=25,
        days_to_expiration=1,
    )

    return {
        "trade": trade,
    }


def get_test_candidates():
    candidates = generate_candidate_condors(
        spx_price=7535.54,
        expected_move=62.5,
        wing_width=25,
        days_to_expiration=1,
    )

    return {
        "requested_dte": 1,
        "count": len(candidates),
        "selected_dte": (
            candidates[0]["sell_put"].get(
                "days_to_expiration"
            )
            if candidates
            else None
        ),
        "expiration_date": (
            candidates[0]["sell_put"].get(
                "expiration_date"
            )
            if candidates
            else None
        ),
        "first": (
            candidates[0]
            if candidates
            else None
        ),
        "last": (
            candidates[-1]
            if candidates
            else None
        ),
    }


def get_test_first_candidate_credit():
    raw_candidates = generate_candidate_condors(
        spx_price=7535.54,
        expected_move=62.5,
        wing_width=25,
        days_to_expiration=1,
    )

    if not raw_candidates:
        return {
            "error": "No candidates",
        }

    trade = normalize_candidate(
        raw_candidates[-1],
        spx_price=7535.54,
        expected_move=62.5,
    )

    credit = calculate_iron_condor_credit(
        trade
    )

    return {
        "trade": trade,
        "credit": credit,
    }


def get_test_candidate_grid():
    results = []

    for dte in [0, 1, 2, 3]:
        for wing in [5, 10, 20, 25]:
            candidates = generate_candidate_condors(
                spx_price=7535.54,
                expected_move=62.5,
                wing_width=wing,
                days_to_expiration=dte,
            )

            results.append(
                {
                    "dte": dte,
                    "wing": wing,
                    "count": len(
                        candidates
                    ),
                }
            )

    return {
        "results": results,
    }


def get_best_trade():
    return build_best_trade(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )


def get_best_bull_put():
    return build_best_bull_put(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )


def get_best_bear_call():
    return build_best_bear_call(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )


def get_strategy_rankings():
    market = run_trade_quality()

    return rank_strategies(
        safe_market_value(
            market,
            "score",
            0,
        ),
        safe_market_value(
            market,
            "trend",
            "UNKNOWN",
        ),
        safe_market_value(
            market,
            "vix_state",
            "UNKNOWN",
        ),
    )