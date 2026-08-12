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


def get_best_trade(
    strategy: str = "auto",
    dte: int = 1,
    wing_width: int = 25,
    contracts: int = 1,
):
    market = run_trade_quality()

    if strategy == "auto":
        rankings = rank_strategies(
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

        supported_strategies = {
            "Iron Condor",
            "Bull Put Credit Spread",
            "Bear Call Credit Spread",
        }

        approved_strategies = [
            item
            for item in rankings
            if (
                item.get("name")
                in supported_strategies
                and item.get("status")
                == "APPROVED"
            )
        ]

        if not approved_strategies:
            return {
                "status": "NO APPROVED STRATEGY",
                "best_trade": None,
                "requested_contracts": contracts,
                "requested_strategy": strategy,
                "requested_dte": dte,
                "requested_wing_width": wing_width,
            }

        selected_strategy = (
            approved_strategies[0]["name"]
        )

    elif strategy == "bull_put_credit_spread":
        selected_strategy = "Bull Put Credit Spread"

    elif strategy == "bear_call_credit_spread":
        selected_strategy = "Bear Call Credit Spread"

    else:
        selected_strategy = "Iron Condor"

    if selected_strategy == "Bull Put Credit Spread":
        result = build_best_bull_put(
            wing_width=wing_width,
            days_to_expiration=dte,
            min_credit=1.00,
        )

    elif selected_strategy == "Bear Call Credit Spread":
        result = build_best_bear_call(
            wing_width=wing_width,
            days_to_expiration=dte,
            min_credit=1.00,
        )

    else:
        result = build_best_trade(
            wing_width=wing_width,
            days_to_expiration=dte,
            min_credit=1.00,
        )

    if isinstance(result, dict):
        result["requested_contracts"] = contracts
        result["requested_strategy"] = strategy
        result["requested_dte"] = dte
        result["requested_wing_width"] = wing_width

        best_trade = result.get("best_trade")

        if not best_trade:
            from bxk_app.option_scanner import (
                get_spx_expiration_status,
            )

            expiration_status = (
                get_spx_expiration_status(dte)
            )

            if (
                expiration_status.get(
                    "chain_available"
                )
                and not expiration_status.get(
                    "exact_available"
                )
            ):
                next_dte = expiration_status.get(
                    "next_available_dte"
                )

                next_expiration = (
                    expiration_status.get(
                        "next_expiration"
                    )
                )

                if (
                    next_dte is not None
                    and next_expiration
                ):
                    message = (
                        f"{dte} DTE expiration unavailable. "
                        "Next listed expiration: "
                        f"{next_expiration} · "
                        f"{next_dte} DTE. "
                        "No substitution was made."
                    )
                else:
                    message = (
                        f"{dte} DTE expiration unavailable. "
                        "No later listed expiration is "
                        "currently available. "
                        "No substitution was made."
                    )

                result["status"] = "NO TRADE"
                result["reason_code"] = (
                    "EXACT_DTE_UNAVAILABLE"
                )
                result["reason"] = message
                result["message"] = message
                result["next_available_dte"] = (
                    next_dte
                )
                result["next_expiration"] = (
                    next_expiration
                )
                result["substitution_made"] = False


        if best_trade:
            final_decision = str(
                best_trade.get(
                    "final_decision",
                    "",
                )
            ).upper()

            market_permission = str(
                best_trade.get(
                    "market_permission",
                    "",
                )
            ).upper()

            if (
                final_decision == "NO TRADE"
                or market_permission == "WAIT"
            ):
                result["status"] = "NO TRADE"
                result["best_trade"] = None
                result["blocked_trade"] = best_trade
                result["message"] = (
                    "Trade blocked by market analysis."
                )

    return result
    
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