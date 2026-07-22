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
# ENVIRONMENT AND HEALTH
# =========================================================


@router.get("/api/test-env")
def test_env():
    return {
        "client_id_loaded": bool(
            os.getenv("TASTYTRADE_CLIENT_ID")
        ),
        "client_secret_loaded": bool(
            os.getenv("TASTYTRADE_CLIENT_SECRET")
        ),
        "refresh_token_loaded": bool(
            os.getenv("TASTYTRADE_REFRESH_TOKEN")
        ),
        "tt_secret_loaded": bool(
            os.getenv("TT_SECRET")
        ),
        "tt_refresh_token_loaded": bool(
            os.getenv("TT_REFRESH_TOKEN")
        ),
    }


@router.get("/health")
def health():
    return {
        "status": "OK",
    }


@router.get("/api/health")
def api_health():
    return {
        "status": "OK",
    }


# =========================================================
# MARKET RECOMMENDATION
# =========================================================


@router.get("/recommend")
def recommend_short():
    return recommend()

@router.get("/api/recommend")
def recommend():
    """
    Return one consistent BXK decision.

    The live analyzed trade is the source of truth for:
    - score
    - grade
    - readiness
    - market regime
    - recommendation
    - final decision

    The older market engine remains available for descriptive
    fields such as trend and VIX state.
    """

    # Refresh live market information.
    try:
        MarketEngine().update()
    except Exception as error:
        pass

    # Older market-condition model.
    # Retained for descriptive fields and fallback behavior.
    market = run_trade_quality()

    # Build the actual live trade.
    try:
        best_trade_result = build_best_trade(
            wing_width=25,
            days_to_expiration=1,
            min_credit=1.00,
        )
    except Exception as error:
        best_trade_result = {
            "status": "ERROR",
            "best_trade": None,
            "message": str(error),
        }

    # build_best_trade() normally returns a wrapper dictionary
    # containing the analyzed trade under "best_trade".
    if isinstance(best_trade_result, dict):
        best_trade = best_trade_result.get(
            "best_trade"
        )

        if not isinstance(best_trade, dict):
            best_trade = {}
    else:
        best_trade_result = {}
        best_trade = {}

    # =====================================================
    # CANONICAL TRADE SCORE
    # =====================================================

    trade_score = safe_market_value(
        best_trade,
        "trade_quality_score",
        None,
    )

    if trade_score is None:
        trade_score = safe_market_value(
            best_trade,
            "trade_score",
            None,
        )

    if trade_score is None:
        trade_score = safe_market_value(
            best_trade,
            "score",
            0,
        )

    try:
        trade_score = int(
            round(float(trade_score or 0))
        )
    except (TypeError, ValueError):
        trade_score = 0

    trade_grade = safe_market_value(
        best_trade,
        "grade",
        None,
    )

    trade_rating = safe_market_value(
        best_trade,
        "rating",
        None,
    )

    trade_quality_label = safe_market_value(
        best_trade,
        "quality_label",
        None,
    )

    if not trade_quality_label:
        if trade_grade and trade_rating:
            trade_quality_label = (
                f"{trade_grade} {trade_rating}"
            )
        else:
            trade_quality_label = "No rated trade"

    final_decision = str(
        safe_market_value(
            best_trade,
            "final_decision",
            "",
        )
        or ""
    ).upper()

    market_permission = str(
        safe_market_value(
            best_trade,
            "market_permission",
            "",
        )
        or ""
    ).upper()

  
    # =====================================================
    # CANONICAL BXK DECISION
    # The analyzed trade decision is the source of truth.
    # =====================================================

    if final_decision == "ENTER TRADE":
        canonical_regime = "TRADE"
        canonical_recommendation = "Trade allowed"

    elif final_decision == "TRADE SMALL":
        canonical_regime = "CAUTION"
        canonical_recommendation = "TRADE SMALL"

    else:
        final_decision = "NO TRADE"
        canonical_regime = "WAIT"
        canonical_recommendation = "No trade"

        # If no live trade score was returned, fall back to the
        # older market-condition score rather than returning zero.
        if trade_score <= 0:
            trade_score = safe_market_value(
            market,
            "score",
            0,
        )

        try:
            trade_score = int(
                round(float(trade_score or 0))
            )
        except (TypeError, ValueError):
            trade_score = 0

        canonical_regime = safe_market_value(
            market,
            "market_regime",
            "WAIT",
        )

        canonical_recommendation = safe_market_value(
            market,
            "recommendation",
            "No trade",
        )

        trade_grade = safe_market_value(
            market,
            "grade",
            trade_grade,
        )

        trade_quality_label = safe_market_value(
            market,
            "quality_label",
            trade_quality_label,
        )

    market_trend = safe_market_value(
        market,
        "trend",
        "UNKNOWN",
    )

    market_vix_state = safe_market_value(
        market,
        "vix_state",
        "UNKNOWN",
    )

    strategies = rank_strategies(
        trade_score,
        market_trend,
        market_vix_state,
    )

    # Keep the old opportunity object for dashboard
    # compatibility. The live best_trade remains authoritative.
    trade_payload = best_trade

    if trade_payload:
        opportunity = {
            "strategy": trade_payload.get(
                "strategy",
                "WAIT",
            ),
            "source": "LIVE",
            "spx_price": trade_payload.get(
                "spx_price"
            ),
            "expected_move": trade_payload.get(
                "expected_move"
            ),
            "sell_put": trade_payload.get(
                "sell_put"
            ),
            "sell_call": trade_payload.get(
                "sell_call"
            ),
            "buy_put": trade_payload.get(
                "buy_put"
            ),
            "buy_call": trade_payload.get(
                "buy_call"
            ),
            "target_credit": trade_payload.get(
                "credit"
            ),
            "pop": trade_payload.get(
                "pop"
            ),
            "risk_level": canonical_regime,
            "trade_score": trade_score,
            "confidence": trade_quality_label,
            "max_risk": trade_payload.get(
                "max_risk"
            ),
            "expected_profit": trade_payload.get(
                "max_profit"
            ),
            "final_decision": final_decision,
            "reasons": trade_payload.get(
                "reasons",
                [],
            ),
        }

    else:
        opportunity = build_opportunity(
            market
        )

    strengths = safe_market_value(
        best_trade,
        "strengths",
        None,
    )

    if strengths is None:
        strengths = safe_market_value(
            market,
            "strengths",
            [],
        )

    weaknesses = safe_market_value(
        best_trade,
        "weaknesses",
        None,
    )

    if weaknesses is None:
        weaknesses = safe_market_value(
            market,
            "weaknesses",
            [],
        )

    reasons = safe_market_value(
        best_trade,
        "reasons",
        None,
    )

    if reasons is None:
        reasons = safe_market_value(
            market,
            "reasons",
            [],
        )

    return {
        "app": "BXK Trader Pro",
        "version": "6.1",
        "routes_version": "CANONICAL_V2",
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
            # One authoritative decision
            "trade": canonical_regime,
            "market_regime": canonical_regime,
            "confidence": trade_score,
            "score": trade_score,
            "recommendation": canonical_recommendation,
            "final_decision": final_decision,

            # Trade-quality explainability
            "grade": trade_grade,
            "quality_label": trade_quality_label,
            "strengths": strengths,
            "weaknesses": weaknesses,

            # Descriptive market fields
            "trend": market_trend,
            "vix_state": market_vix_state,
            "expected_move_state": safe_market_value(
                market,
                "expected_move_state",
                "UNKNOWN",
            ),
            "iv_rank_state": safe_market_value(
                market,
                "iv_rank_state",
                "UNKNOWN",
            ),
            "reasons": reasons,

            "strategies": strategies,

            # Legacy compatibility
            "opportunity": opportunity,

            # Full live result plus extracted live trade
            "best_trade_result": best_trade_result,
            "best_trade": best_trade,
        }

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


@router.get("/api/refresh-market")
def refresh_market():
    market_engine.refresh()

    return {
        "status": "market refresh complete",
        "market_engine": market_engine.get_status(),
        "market_snapshot": market_data.get_snapshot(),
    }


@router.get("/api/market-brief")
def market_brief():
    market = run_trade_quality()
    
    best_trade = build_best_trade(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )

    market_regime = safe_market_value(
        market,
        "market_regime",
        "WAIT",
    )

    trend = safe_market_value(
        market,
        "trend",
        "UNKNOWN",
    )

    vix_state = safe_market_value(
        market,
        "vix_state",
        "UNKNOWN",
    )

    expected_move_state = safe_market_value(
        market,
        "expected_move_state",
        "UNKNOWN",
    )

    iv_rank_state = safe_market_value(
        market,
        "iv_rank_state",
        "UNKNOWN",
    )

    if market_regime == "TRADE":
        summary = (
            f"Market conditions support trading. "
            f"Trend is {trend}, "
            f"VIX is {vix_state}, "
            f"expected move is {expected_move_state}, "
            f"and IV rank is {iv_rank_state}. "
            f"Current conditions favor premium-selling strategies."
        )
    else:
        summary = (
            f"Market conditions are not ideal. "
            f"Trend is {trend}, "
            f"VIX is {vix_state}, "
            f"expected move is {expected_move_state}, "
            f"and IV rank is {iv_rank_state}. "
            f"Waiting is favored until conditions improve."
        )

    return {
        "title": "Market Narrative",
        "summary": summary,
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
    }


@router.get("/api/live-market")
def live_market():
    return market_engine.update()


@router.get("/api/debug/market")
def debug_market():
    return {
        "status": "OK",
        "spx": market_data.spx,
        "vix": market_data.vix,
        "vix1d": market_data.vix1d,
        "expected_move": market_data.expected_move,
        "snapshot": market_data.get_snapshot(),
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
