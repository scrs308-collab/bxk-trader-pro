import os
from datetime import datetime

from fastapi import APIRouter

from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.brokers.tastytrade import broker as new_tastytrade_broker
from bxk_app.market_engine import MarketEngine
from bxk_app.live_option_engine import calculate_iron_condor_credit
from bxk_app.market_data import market_data
from bxk_app.market_engine import market_engine
from bxk_app.opportunity_engine import build_opportunity
from bxk_app.option_scanner import (
    generate_candidate_condors,
    normalize_candidate,
)
from bxk_app.scanner_engine import find_best_iron_condor
from bxk_app.scoring import run_trade_quality
from bxk_app.strategy_ranker import rank_strategies
from bxk_app.tastytrade_client import tastytrade_client
from bxk_app.wing_optimizer import find_best_trade
from bxk_app.position_monitor import build_iron_condor_summary
from bxk_app.trade_builder import (
    build_best_trade,
    build_best_bull_put,
    build_best_bear_call,
)
router = APIRouter()


def safe_market_value(market, field_name, default=None):
    """
    Safely read a value from either an object or dictionary.
    """

    if isinstance(market, dict):
        return market.get(field_name, default)

    return getattr(market, field_name, default)


# =========================================================
# MARKET RECOMMENDATION
# =========================================================


# =========================================================
# MARKET DEBUGGING
# =========================================================


@router.get("/api/debug")
def debug():
    return {
        "app": "BXK Trader Pro",
        "version": "6.1",
        "status": "debug route active",
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "market_engine": market_engine.get_status(),
        "market_snapshot": market_data.get_snapshot(),
    }

    
# =========================================================
# TASTYTRADE ACCOUNT TESTS
# =========================================================


@router.get("/api/test-tastytrade")
def test_tastytrade():
    connected = tastytrade_client.connect()

    return {
        "connected": connected,
        "status": tastytrade_client.get_status(),
        "accounts": tastytrade_client.get_accounts(),
    }


@router.get("/api/test-tastytrade-rest")
def test_tastytrade_rest():
    connected = tastytrade_api.authenticate()

    accounts = (
        tastytrade_api.get_accounts()
        if connected
        else []
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "accounts": accounts,
    }


@router.get("/api/test-tastytrade-balances")
def test_tastytrade_balances():
    connected = tastytrade_api.authenticate()

    balances = (
        tastytrade_api.get_balances()
        if connected
        else None
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "balances": balances,
    }


@router.get("/api/test-tastytrade-positions")
def test_tastytrade_positions():
    connected = tastytrade_api.authenticate()

    positions = (
        tastytrade_api.get_positions()
        if connected
        else []
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "positions": positions,
    }


@router.get("/api/positions-summary")
def positions_summary():
    connected = tastytrade_api.authenticate()

    positions = (
        tastytrade_api.get_position_summary()
        if connected
        else []
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "count": len(positions),
        "positions": positions,
    }


@router.get("/api/account-summary")
def account_summary():
    connected = tastytrade_api.authenticate()

    account = (
        tastytrade_api.get_account_summary()
        if connected
        else None
    )

    return {
        "connected": connected,
        "account": account,
    }


@router.get("/api/test-quote/{symbol}")
def test_quote(symbol: str):
    connected = tastytrade_api.authenticate()

    quote = (
        tastytrade_api.get_quote(
            symbol.upper()
        )
        if connected
        else None
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "symbol": symbol.upper(),
        "quote": quote,
    }


@router.get("/api/test-new-broker")
def test_new_broker():
    connected = new_tastytrade_broker.authenticate()

    return {
        "connected": connected,
        "status": new_tastytrade_broker.get_status(),
        "account": (
            new_tastytrade_broker.get_account_summary()
            if connected
            else None
        ),
        "spx": (
            new_tastytrade_broker.get_quote("SPX")
            if connected
            else None
        ),
        "vix": (
            new_tastytrade_broker.get_quote("VIX")
            if connected
            else None
        ),
    }


# =========================================================
# OPTION CHAIN TESTS
# =========================================================


@router.get("/api/test-spx-chain")
def test_spx_chain():
    connected = tastytrade_api.authenticate()

    chain = (
        tastytrade_api.get_spx_option_chain()
        if connected
        else None
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "has_chain": bool(chain),
        "chain_keys": (
            list(chain.keys())
            if isinstance(chain, dict)
            else None
        ),
        "chain_preview": chain,
    }


@router.get("/api/test-spx-chain-shape")
def test_spx_chain_shape():
    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return {
            "error": "No chain",
        }

    items = chain.get("items", [])

    if not items:
        return {
            "error": "Chain has no items",
        }

    expirations = items[0].get(
        "expirations",
        [],
    )

    if not expirations:
        return {
            "error": "Chain has no expirations",
        }

    strikes = expirations[0].get(
        "strikes",
        [],
    )

    if not strikes:
        return {
            "error": "Expiration has no strikes",
        }

    expiration = expirations[0]
    strike = strikes[0]

    return {
        "item_keys": list(
            items[0].keys()
        ),
        "expiration_keys": list(
            expiration.keys()
        ),
        "strike_keys": list(
            strike.keys()
        ),
        "first_expiration": {
            "expiration_type": expiration.get(
                "expiration-type"
            ),
            "expiration_date": expiration.get(
                "expiration-date"
            ),
            "days_to_expiration": expiration.get(
                "days-to-expiration"
            ),
            "settlement_type": expiration.get(
                "settlement-type"
            ),
        },
        "first_strike": strike,
    }


@router.get("/api/test-spx-option-quotes")
def test_spx_option_quotes():
    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return {
            "error": "No chain",
        }

    item = chain["items"][0]
    expiration = item["expirations"][0]
    strikes = expiration["strikes"]

    sample_symbols = []

    for strike in strikes:
        price = float(
            strike["strike-price"]
        )

        if 7450 <= price <= 7625:
            sample_symbols.append(
                strike["put-streamer-symbol"]
            )
            sample_symbols.append(
                strike["call-streamer-symbol"]
            )

        if len(sample_symbols) >= 10:
            break

    quotes = tastytrade_api.get_option_quotes(
        sample_symbols
    )

    return {
        "using": "streamer-symbols",
        "sample_symbols": sample_symbols,
        "quote_count": len(quotes),
        "quotes": quotes,
        "status": tastytrade_api.get_status(),
    }


@router.get("/api/test-expirations")
def test_expirations():
    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return {
            "error": "No chain",
        }

    item = chain["items"][0]

    return {
        "expirations": [
            {
                "date": expiration.get(
                    "expiration-date"
                ),
                "dte": expiration.get(
                    "days-to-expiration"
                ),
                "type": expiration.get(
                    "expiration-type"
                ),
                "settlement": expiration.get(
                    "settlement-type"
                ),
                "strike_count": len(
                    expiration.get(
                        "strikes",
                        [],
                    )
                ),
            }
            for expiration in item.get(
                "expirations",
                [],
            )[:10]
        ]
    }


# =========================================================
# SCANNER AND TRADE TESTS
# =========================================================


@router.get("/api/test-wing-optimizer")
def test_wing_optimizer():
    trade = find_best_trade(
        spx_price=7535.54,
        expected_move=62.5,
    )

    return {
        "trade": trade,
    }


@router.get("/api/test-scanner-engine")
def test_scanner_engine():
    trade = find_best_iron_condor(
        spx_price=7535.54,
        expected_move=62.5,
        wing_width=25,
        days_to_expiration=1,
    )

    return {
        "trade": trade,
    }


@router.get("/api/test-candidates")
def test_candidates():
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


@router.get("/api/test-first-candidate-credit")
def test_first_candidate_credit():
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


@router.get("/api/test-candidate-grid")
def test_candidate_grid():
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


@router.get("/api/best-trade")
def best_trade():
    return build_best_trade(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )

@router.get("/api/best-bull-put")
def best_bull_put():
    return build_best_bull_put(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )

@router.get("/api/best-bear-call")
def best_bear_call():
    return build_best_bear_call(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )

@router.get("/api/strategy-rankings")
def strategy_rankings():
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


# =========================================================
# LEGACY REST OPTION QUOTE TEST
# =========================================================
@router.get("/api/position-monitor")
def position_monitor():
    """
    Return open SPX option legs grouped into one
    Iron Condor position summary.
    """

    try:
        positions = tastytrade_api.get_position_summary()

        if not positions:
            return {
                "status": "EMPTY",
                "connected": tastytrade_api.get_status().get("connected", False),
                "position": None,
                "message": "No open positions found.",
            }

        snapshot = market_data.get_snapshot()

        spx_price = (
            (snapshot or {}).get("spx")
            or (snapshot or {}).get("spx_price")
            or (snapshot or {}).get("price")
        )

        # If the cached snapshot has no SPX price,
        # ask the market engine for a fresh update.
        if not spx_price:
            try:
                live_market = market_engine.update()

                if isinstance(live_market, dict):
                    spx_price = (
                        live_market.get("spx")
                        or live_market.get("spx_price")
                        or live_market.get("price")
                    )

            except Exception:
                spx_price = None

        try:
            spx_price = float(spx_price)
        except (TypeError, ValueError):
            spx_price = None

        if spx_price is not None and spx_price <= 0:
            spx_price = None

        summary = build_iron_condor_summary(
            positions=positions,
            spx_price=spx_price,
        )

        if not summary:
            return {
                "status": "UNSUPPORTED",
                "connected": tastytrade_api.get_status().get("connected", False),
                "position": None,
                "leg_count": len(positions),
                "message": (
                    "Open positions could not be grouped "
                    "into one Iron Condor."
                ),
            }

        return {
            "status": "OK",
            "connected": tastytrade_api.get_status().get("connected", False),
            "position": summary,
        }

    except Exception as error:
        return {
            "status": "ERROR",
            "connected": False,
            "position": None,
            "message": str(error),
        }

@router.get("/api/test-option-quote-fields")
def test_option_quote_fields():
    result = build_best_trade(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )

    trade = result.get(
        "best_trade"
    )

    if not trade:
        return {
            "error": "No best trade returned",
            "result": result,
        }

    symbols = [
        trade.get("sell_put_symbol"),
        trade.get("buy_put_symbol"),
        trade.get("sell_call_symbol"),
        trade.get("buy_call_symbol"),
    ]

    symbols = [
        symbol
        for symbol in symbols
        if symbol
    ]

    quotes = tastytrade_api.get_option_quotes(
        symbols
    )

    return {
        "symbols_sent": symbols,
        "quote_count": len(quotes),
        "first_quote_keys": (
            list(quotes[0].keys())
            if quotes
            else []
        ),
        "quotes": quotes,
        "status": tastytrade_api.get_status(),
    }
