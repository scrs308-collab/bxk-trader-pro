from datetime import datetime

from bxk_app.live_option_engine import (
    calculate_bear_call_credit,
    calculate_bull_put_credit,
    calculate_iron_condor_credit,
)
from bxk_app.market_data import market_data
from bxk_app.option_scanner import (
    generate_bear_call_candidates,
    generate_bull_put_candidates,
    generate_candidate_condors,
    normalize_bear_call_candidate,
    normalize_bull_put_candidate,
    normalize_candidate,
)
from bxk_app.scoring import run_trade_quality
from bxk_app.trade_analyzer import analyze_trade


def build_demo_trade(
    spx_price: float = 7535.54,
    expected_move: float = 62.5,
    wing_width: int = 25,
):
    """
    Return a demo Iron Condor when live candidates are unavailable.
    """

    sell_put = round(
        (spx_price - expected_move) / 5
    ) * 5

    buy_put = sell_put - wing_width

    sell_call = round(
        (spx_price + expected_move) / 5
    ) * 5

    buy_call = sell_call + wing_width

    credit = 2.30

    max_profit = round(
        credit * 100,
        2,
    )

    max_risk = round(
        (wing_width - credit) * 100,
        2,
    )

    best_trade = {
        "strategy": "SPX Iron Condor",
        "symbol": "SPX",
        "dte": 1,
        "spx_price": round(
            float(spx_price),
            2,
        ),
        "expected_move": round(
            float(expected_move),
            2,
        ),
        "sell_put": sell_put,
        "buy_put": buy_put,
        "sell_call": sell_call,
        "buy_call": buy_call,
        "wing_width": wing_width,
        "credit": credit,
        "max_profit": max_profit,
        "max_risk": max_risk,
        "risk_reward": (
            round(
                max_risk / max_profit,
                2,
            )
            if max_profit
            else None
        ),
        "pop": 84,
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    analysis = analyze_trade(
        best_trade
    )

    best_trade.update(
        analysis
    )

    return {
        "status": "DEMO",
        "reason": (
            "Market is closed or live option chain unavailable"
        ),
        "best_trade": best_trade,
    }


def build_best_trade(
    wing_width: int = 25,
    days_to_expiration: int = 1,
    min_credit: float = 1.00,
):
    """
    Build, price, analyze, and rank live SPX Iron Condors.
    """

    market = run_trade_quality()
    snapshot = market_data.get_snapshot()

    spx_price = (
        snapshot.get("spx")
        or snapshot.get("price")
    )

    expected_move = snapshot.get(
        "expected_move"
    )

    try:
        spx_price = float(
            spx_price
        )
    except (TypeError, ValueError):
        spx_price = 7535.54

    if spx_price <= 0:
        spx_price = 7535.54

    try:
        expected_move = float(
            expected_move
        )
    except (TypeError, ValueError):
        expected_move = 62.5

    if expected_move <= 0:
        expected_move = 62.5

    raw_candidates = generate_candidate_condors(
        spx_price=spx_price,
        expected_move=expected_move,
        wing_width=wing_width,
        days_to_expiration=days_to_expiration,
    )

    if not raw_candidates:
        return build_demo_trade(
            spx_price=spx_price,
            expected_move=expected_move,
            wing_width=wing_width,
        )

    ranked = []

    for candidate in raw_candidates:
        trade = normalize_candidate(
            candidate,
            spx_price=spx_price,
            expected_move=expected_move,
        )

        credit_data = calculate_iron_condor_credit(
            trade
        )

        credit = (
            credit_data.get(
                "live_credit"
            )
            or credit_data.get(
                "credit"
            )
            or 0
        )

        try:
            credit = float(
                credit
            )
        except (TypeError, ValueError):
            credit = 0.0

        if credit < min_credit:
            continue

        sell_put = trade["sell_put"]
        buy_put = trade["buy_put"]
        sell_call = trade["sell_call"]
        buy_call = trade["buy_call"]

        actual_wing_width = int(
            trade.get(
                "wing_width",
                wing_width,
            )
        )

        if credit >= actual_wing_width:
            continue

        max_profit = round(
            credit * 100,
            2,
        )

        max_risk = round(
            (
                actual_wing_width
                - credit
            )
            * 100,
            2,
        )

        put_distance = round(
            spx_price - sell_put,
            2,
        )

        call_distance = round(
            sell_call - spx_price,
            2,
        )

        candidate_rank_score = round(
            market.score
            + min(
                put_distance,
                call_distance,
            )
            + min(
                credit * 10,
                25,
            ),
            2,
        )

        best_candidate = {
            "strategy": "SPX Iron Condor",
            "symbol": "SPX",
            "dte": trade.get(
                "dte",
                days_to_expiration,
            ),
            "expiration": trade.get(
                "expiration"
            ),
            "settlement_type": trade.get(
                "settlement_type"
            ),
            "spx_price": round(
                spx_price,
                2,
            ),
            "expected_move": round(
                expected_move,
                2,
            ),
            "sell_put": sell_put,
            "buy_put": buy_put,
            "sell_call": sell_call,
            "buy_call": buy_call,
            "sell_put_symbol": trade.get(
                "sell_put_symbol"
            ),
            "buy_put_symbol": trade.get(
                "buy_put_symbol"
            ),
            "sell_call_symbol": trade.get(
                "sell_call_symbol"
            ),
            "buy_call_symbol": trade.get(
                "buy_call_symbol"
            ),
            "sell_put_streamer": trade.get(
                "sell_put_streamer"
            ),
            "buy_put_streamer": trade.get(
                "buy_put_streamer"
            ),
            "sell_call_streamer": trade.get(
                "sell_call_streamer"
            ),
            "buy_call_streamer": trade.get(
                "buy_call_streamer"
            ),
            "wing_width": actual_wing_width,
            "credit": round(
                credit,
                2,
            ),
            "max_profit": max_profit,
            "max_risk": max_risk,
            "risk_reward": (
                round(
                    max_risk / max_profit,
                    2,
                )
                if max_profit
                else None
            ),
            "put_distance": put_distance,
            "call_distance": call_distance,
            "candidate_rank_score": (
                candidate_rank_score
            ),
            "pop": 84,
            "market_score": market.score,
            "market_regime": (
                market.market_regime
            ),
            "trend": market.trend,
            "vix_state": market.vix_state,
            "expected_move_state": (
                market.expected_move_state
            ),
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "credit_details": credit_data,
        }

        if credit_data.get(
            "pop"
        ) is not None:
            best_candidate["pop"] = (
                credit_data["pop"]
            )

        if credit_data.get(
            "probability_of_touch"
        ) is not None:
            best_candidate[
                "probability_of_touch"
            ] = credit_data[
                "probability_of_touch"
            ]

        if credit_data.get(
            "short_put_delta"
        ) is not None:
            best_candidate[
                "short_put_delta"
            ] = credit_data[
                "short_put_delta"
            ]

        if credit_data.get(
            "short_call_delta"
        ) is not None:
            best_candidate[
                "short_call_delta"
            ] = credit_data[
                "short_call_delta"
            ]

        analysis = analyze_trade(
            best_candidate
        )

        best_candidate.update(
            analysis
        )

        ranked.append(
            best_candidate
        )

    if not ranked:
        return build_demo_trade(
            spx_price=spx_price,
            expected_move=expected_move,
            wing_width=wing_width,
        )

    ranked.sort(
        key=lambda item: item["trade_score"],
        reverse=True,
    )

    return {
        "status": "OK",
        "best_trade": ranked[0],
        "candidate_count": len(
            ranked
        ),
        "top_candidates": ranked[:5],
    }


def build_best_bull_put(
    wing_width: int = 25,
    days_to_expiration: int = 1,
    min_credit: float = 1.00,
    min_short_delta: float = 0.10,
    max_short_delta: float = 0.25,
):
    """
    Build, price, filter, analyze, and rank live Bull Put spreads.
    """

    market = run_trade_quality()
    snapshot = market_data.get_snapshot()

    spx_price = (
        snapshot.get("spx")
        or snapshot.get("price")
        or 7535.54
    )

    expected_move = (
        snapshot.get("expected_move")
        or 62.5
    )

    try:
        spx_price = float(
            spx_price
        )
    except (TypeError, ValueError):
        spx_price = 7535.54

    if spx_price <= 0:
        spx_price = 7535.54

    try:
        expected_move = float(
            expected_move
        )
    except (TypeError, ValueError):
        expected_move = 62.5

    if expected_move <= 0:
        expected_move = 62.5

    raw_candidates = generate_bull_put_candidates(
        wing_width=wing_width,
        days_to_expiration=days_to_expiration,
    )

    diagnostics = {
        "candidates_generated": len(
            raw_candidates
        ),
        "missing_delta": 0,
        "invalid_delta": 0,
        "delta_too_low": 0,
        "delta_too_high": 0,
        "credit_too_low": 0,
        "invalid_credit": 0,
        "invalid_risk": 0,
        "qualified": 0,
        "lowest_delta": None,
        "highest_delta": None,
        "highest_credit": 0.0,
    }

    if not raw_candidates:
        return {
            "status": "NO CANDIDATES",
            "best_trade": None,
            "filters": {
                "min_credit": min_credit,
                "min_short_delta": (
                    min_short_delta
                ),
                "max_short_delta": (
                    max_short_delta
                ),
            },
            "diagnostics": diagnostics,
        }

    ranked = []

    for candidate in raw_candidates:
        trade = normalize_bull_put_candidate(
            candidate,
            spx_price=spx_price,
            expected_move=expected_move,
        )

        credit_data = calculate_bull_put_credit(
            trade
        )

        short_put_delta = credit_data.get(
            "short_put_delta"
        )

        if short_put_delta is None:
            diagnostics["missing_delta"] += 1
            continue

        try:
            short_put_delta = abs(
                float(short_put_delta)
            )
        except (TypeError, ValueError):
            diagnostics["invalid_delta"] += 1
            continue

        if (
            diagnostics["lowest_delta"] is None
            or short_put_delta
            < diagnostics["lowest_delta"]
        ):
            diagnostics["lowest_delta"] = (
                short_put_delta
            )

        if (
            diagnostics["highest_delta"] is None
            or short_put_delta
            > diagnostics["highest_delta"]
        ):
            diagnostics["highest_delta"] = (
                short_put_delta
            )

        if short_put_delta < min_short_delta:
            diagnostics["delta_too_low"] += 1
            continue

        if short_put_delta > max_short_delta:
            diagnostics["delta_too_high"] += 1
            continue

        try:
            credit = float(
                credit_data.get(
                    "live_credit",
                    0,
                )
            )
        except (TypeError, ValueError):
            credit = 0.0

        diagnostics["highest_credit"] = max(
            diagnostics["highest_credit"],
            credit,
        )

        if credit <= 0:
            diagnostics["invalid_credit"] += 1
            continue

        if credit < min_credit:
            diagnostics["credit_too_low"] += 1
            continue

        sell_put = trade["sell_put"]
        buy_put = trade["buy_put"]

        actual_wing_width = int(
            trade.get(
                "wing_width",
                wing_width,
            )
        )

        if (
            actual_wing_width <= 0
            or credit >= actual_wing_width
        ):
            diagnostics["invalid_risk"] += 1
            continue

        max_profit = round(
            credit * 100,
            2,
        )

        max_risk = round(
            (
                actual_wing_width
                - credit
            )
            * 100,
            2,
        )

        put_distance = round(
            spx_price - sell_put,
            2,
        )

        candidate_trade = {
            "strategy": (
                "Bull Put Credit Spread"
            ),
            "symbol": "SPX",
            "dte": trade.get(
                "dte",
                days_to_expiration,
            ),
            "expiration": trade.get(
                "expiration"
            ),
            "settlement_type": trade.get(
                "settlement_type"
            ),
            "spx_price": round(
                spx_price,
                2,
            ),
            "expected_move": round(
                expected_move,
                2,
            ),
            "sell_put": sell_put,
            "buy_put": buy_put,
            "sell_put_symbol": trade.get(
                "sell_put_symbol"
            ),
            "buy_put_symbol": trade.get(
                "buy_put_symbol"
            ),
            "sell_put_streamer": trade.get(
                "sell_put_streamer"
            ),
            "buy_put_streamer": trade.get(
                "buy_put_streamer"
            ),
            "wing_width": actual_wing_width,
            "credit": round(
                credit,
                2,
            ),
            "max_profit": max_profit,
            "max_risk": max_risk,
            "risk_reward": (
                round(
                    max_risk / max_profit,
                    2,
                )
                if max_profit
                else None
            ),
            "put_distance": put_distance,
            "short_put_delta": (
                short_put_delta
            ),
            "market_score": market.score,
            "market_regime": (
                market.market_regime
            ),
            "trend": market.trend,
            "vix_state": market.vix_state,
            "expected_move_state": (
                market.expected_move_state
            ),
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "credit_details": credit_data,
        }

        candidate_trade.update(
            credit_data
        )

        candidate_trade[
            "short_put_delta"
        ] = short_put_delta

        analysis = analyze_trade(
            candidate_trade
        )

        candidate_trade.update(
            analysis
        )

        diagnostics["qualified"] += 1

        ranked.append(
            candidate_trade
        )

    if not ranked:
        return {
            "status": "NO QUALIFYING TRADES",
            "best_trade": None,
            "filters": {
                "min_credit": min_credit,
                "min_short_delta": (
                    min_short_delta
                ),
                "max_short_delta": (
                    max_short_delta
                ),
            },
            "diagnostics": diagnostics,
        }

    ranked.sort(
        key=lambda item: item["trade_score"],
        reverse=True,
    )

    return {
        "status": "OK",
        "best_trade": ranked[0],
        "candidate_count": len(
            ranked
        ),
        "top_candidates": ranked[:5],
        "filters": {
            "min_credit": min_credit,
            "min_short_delta": (
                min_short_delta
            ),
            "max_short_delta": (
                max_short_delta
            ),
        },
        "diagnostics": diagnostics,
    }

def build_best_bear_call(
    wing_width: int = 25,
    days_to_expiration: int = 1,
    min_credit: float = 1.00,
    min_short_delta: float = 0.10,
    max_short_delta: float = 0.25,
):
    """
    Build, price, filter, analyze, and rank live Bear Call spreads.
    """

    market = run_trade_quality()
    snapshot = market_data.get_snapshot()

    spx_price = (
        snapshot.get("spx")
        or snapshot.get("price")
        or 7535.54
    )

    expected_move = (
        snapshot.get("expected_move")
        or 62.5
    )

    try:
        spx_price = float(spx_price)
    except (TypeError, ValueError):
        spx_price = 7535.54

    if spx_price <= 0:
        spx_price = 7535.54

    try:
        expected_move = float(expected_move)
    except (TypeError, ValueError):
        expected_move = 62.5

    if expected_move <= 0:
        expected_move = 62.5

    raw_candidates = generate_bear_call_candidates(
        wing_width=wing_width,
        days_to_expiration=days_to_expiration,
    )

    diagnostics = {
        "candidates_generated": len(raw_candidates),
        "missing_delta": 0,
        "invalid_delta": 0,
        "delta_too_low": 0,
        "delta_too_high": 0,
        "credit_too_low": 0,
        "invalid_credit": 0,
        "invalid_risk": 0,
        "qualified": 0,
        "lowest_delta": None,
        "highest_delta": None,
        "highest_credit": 0.0,
    }

    if not raw_candidates:
        return {
            "status": "NO CANDIDATES",
            "best_trade": None,
            "filters": {
                "min_credit": min_credit,
                "min_short_delta": min_short_delta,
                "max_short_delta": max_short_delta,
            },
            "diagnostics": diagnostics,
        }

    ranked = []

    for candidate in raw_candidates:
        trade = normalize_bear_call_candidate(
            candidate,
            spx_price=spx_price,
            expected_move=expected_move,
        )

        credit_data = calculate_bear_call_credit(trade)

        short_call_delta = credit_data.get(
            "short_call_delta"
        )

        if short_call_delta is None:
            diagnostics["missing_delta"] += 1
            continue

        try:
            short_call_delta = abs(
                float(short_call_delta)
            )
        except (TypeError, ValueError):
            diagnostics["invalid_delta"] += 1
            continue

        if (
            diagnostics["lowest_delta"] is None
            or short_call_delta
            < diagnostics["lowest_delta"]
        ):
            diagnostics["lowest_delta"] = short_call_delta

        if (
            diagnostics["highest_delta"] is None
            or short_call_delta
            > diagnostics["highest_delta"]
        ):
            diagnostics["highest_delta"] = short_call_delta

        if short_call_delta < min_short_delta:
            diagnostics["delta_too_low"] += 1
            continue

        if short_call_delta > max_short_delta:
            diagnostics["delta_too_high"] += 1
            continue

        try:
            credit = float(
                credit_data.get("live_credit", 0)
            )
        except (TypeError, ValueError):
            credit = 0.0

        diagnostics["highest_credit"] = max(
            diagnostics["highest_credit"],
            credit,
        )

        if credit <= 0:
            diagnostics["invalid_credit"] += 1
            continue

        if credit < min_credit:
            diagnostics["credit_too_low"] += 1
            continue

        sell_call = trade["sell_call"]
        buy_call = trade["buy_call"]

        actual_wing_width = int(
            trade.get("wing_width", wing_width)
        )

        if (
            actual_wing_width <= 0
            or credit >= actual_wing_width
        ):
            diagnostics["invalid_risk"] += 1
            continue

        max_profit = round(credit * 100, 2)

        max_risk = round(
            (actual_wing_width - credit) * 100,
            2,
        )

        call_distance = round(
            sell_call - spx_price,
            2,
        )

        candidate_trade = {
            "strategy": "Bear Call Credit Spread",
            "symbol": "SPX",
            "dte": trade.get(
                "dte",
                days_to_expiration,
            ),
            "expiration": trade.get("expiration"),
            "settlement_type": trade.get(
                "settlement_type"
            ),
            "spx_price": round(spx_price, 2),
            "expected_move": round(
                expected_move,
                2,
            ),
            "sell_call": sell_call,
            "buy_call": buy_call,
            "sell_call_symbol": trade.get(
                "sell_call_symbol"
            ),
            "buy_call_symbol": trade.get(
                "buy_call_symbol"
            ),
            "sell_call_streamer": trade.get(
                "sell_call_streamer"
            ),
            "buy_call_streamer": trade.get(
                "buy_call_streamer"
            ),
            "wing_width": actual_wing_width,
            "credit": round(credit, 2),
            "max_profit": max_profit,
            "max_risk": max_risk,
            "risk_reward": (
                round(max_risk / max_profit, 2)
                if max_profit
                else None
            ),
            "call_distance": call_distance,
            "short_call_delta": short_call_delta,
            "market_score": market.score,
            "market_regime": market.market_regime,
            "trend": market.trend,
            "vix_state": market.vix_state,
            "expected_move_state": (
                market.expected_move_state
            ),
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "credit_details": credit_data,
        }

        candidate_trade.update(credit_data)
        candidate_trade[
            "short_call_delta"
        ] = short_call_delta

        analysis = analyze_trade(candidate_trade)
        candidate_trade.update(analysis)

        diagnostics["qualified"] += 1
        ranked.append(candidate_trade)

    if not ranked:
        return {
            "status": "NO QUALIFYING TRADES",
            "best_trade": None,
            "filters": {
                "min_credit": min_credit,
                "min_short_delta": min_short_delta,
                "max_short_delta": max_short_delta,
            },
            "diagnostics": diagnostics,
        }

    ranked.sort(
        key=lambda item: item["trade_score"],
        reverse=True,
    )

    return {
        "status": "OK",
        "best_trade": ranked[0],
        "candidate_count": len(ranked),
        "top_candidates": ranked[:5],
        "filters": {
            "min_credit": min_credit,
            "min_short_delta": min_short_delta,
            "max_short_delta": max_short_delta,
        },
        "diagnostics": diagnostics,
    }