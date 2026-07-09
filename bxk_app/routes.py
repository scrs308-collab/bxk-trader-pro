from bxk_app.market_engine import market_engine
from datetime import datetime
from bxk_app.trade_builder import build_best_trade
from fastapi import APIRouter
from bxk_app.option_scanner import generate_candidate_condors, normalize_candidate
from bxk_app.live_option_engine import calculate_iron_condor_credit
from bxk_app.market_data import market_data
from bxk_app.scoring import run_trade_quality
from bxk_app.strategy_ranker import rank_strategies
from bxk_app.tastytrade_client import tastytrade_client
from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.brokers.tastytrade import broker as new_tastytrade_broker
from bxk_app.opportunity_engine import build_opportunity
from bxk_app.scanner_engine import find_best_iron_condor
from bxk_app.option_scanner import generate_candidate_condors
from bxk_app.wing_optimizer import find_best_trade
from bxk_app.strategy_ranking_engine import rank_strategies
router = APIRouter()

@router.get("/api/test-env")
def test_env():
    import os

    return {
        "client_id_loaded": bool(os.getenv("TASTYTRADE_CLIENT_ID")),
        "client_secret_loaded": bool(os.getenv("TASTYTRADE_CLIENT_SECRET")),
        "refresh_token_loaded": bool(os.getenv("TASTYTRADE_REFRESH_TOKEN")),
        "tt_secret_loaded": bool(os.getenv("TT_SECRET")),
        "tt_refresh_token_loaded": bool(os.getenv("TT_REFRESH_TOKEN")),
    }

@router.get("/health")
def health():
    return {"status": "OK"}


@router.get("/api/health")
def api_health():
    return {"status": "OK"}


@router.get("/recommend")
def recommend_short():
    return recommend()


@router.get("/api/recommend")
def recommend():
    market = run_trade_quality()

    strategies = rank_strategies(
        market.score,
        market.trend,
        market.vix_state,
    )

    opportunity = build_opportunity(market)

    return {
        "app": "BXK Trader Pro",
        "version": "6.1",
        "status": "OK",
        "timestamp": datetime.now().isoformat(timespec="seconds"),

        "trade": market.market_regime,
        "market_regime": market.market_regime,
        "confidence": market.confidence,
        "score": market.score,
        "trend": market.trend,
        "vix_state": market.vix_state,
        "expected_move_state": market.expected_move_state,
        "iv_rank_state": market.iv_rank_state,
        "recommendation": market.recommendation,
        "reasons": market.reasons,

        "strategies": strategies,
        "opportunity": opportunity,
    }


@router.get("/api/debug")
def debug():
    return {
        "app": "BXK Trader Pro",
        "version": "6.0",
        "status": "debug route active",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
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

    if market.market_regime == "TRADE":
        summary = (
            f"Market conditions support trading. Trend is {market.trend}, "
            f"VIX is {market.vix_state}, expected move is {market.expected_move_state}, "
            f"and IV rank is {market.iv_rank_state}. Current setup favors premium-selling strategies."
        )
    else:
        summary = (
            f"Market conditions are not ideal. Trend is {market.trend}, "
            f"VIX is {market.vix_state}, expected move is {market.expected_move_state}, "
            f"and IV rank is {market.iv_rank_state}. Waiting is favored until conditions improve."
        )

    return {
        "title": "Market Narrative",
        "summary": summary,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

@router.get("/api/live-market")
def live_market():
    return market_engine.update()

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
    accounts = tastytrade_api.get_accounts() if connected else []

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "accounts": accounts,
    }

@router.get("/api/test-tastytrade-balances")
def test_tastytrade_balances():
    connected = tastytrade_api.authenticate()
    balances = tastytrade_api.get_balances() if connected else None

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "balances": balances,
    }
@router.get("/api/test-tastytrade-positions")
def test_tastytrade_positions():
    connected = tastytrade_api.authenticate()
    positions = tastytrade_api.get_positions() if connected else []

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "positions": positions,
    }

@router.get("/api/positions-summary")
def positions_summary():
    connected = tastytrade_api.authenticate()
    positions = tastytrade_api.get_position_summary() if connected else []

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "count": len(positions),
        "positions": positions,
    }
@router.get("/api/test-wing-optimizer")
def test_wing_optimizer():
    trade = find_best_trade(
        spx_price=7535.54,
        expected_move=62.5,
    )

    return {
        "trade": trade,
    }
@router.get("/api/account-summary")
def account_summary():
    connected = tastytrade_api.authenticate()

    return {
        "connected": connected,
        "account": tastytrade_api.get_account_summary() if connected else None,
    }

@router.get("/api/test-quote/{symbol}")
def test_quote(symbol: str):
    connected = tastytrade_api.authenticate()
    quote = tastytrade_api.get_quote(symbol.upper()) if connected else None

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
        "account": new_tastytrade_broker.get_account_summary() if connected else None,
        "spx": new_tastytrade_broker.get_quote("SPX") if connected else None,
        "vix": new_tastytrade_broker.get_quote("VIX") if connected else None,
    }
@router.get("/api/test-spx-chain")
def test_spx_chain():
    connected = tastytrade_api.authenticate()
    chain = tastytrade_api.get_spx_option_chain() if connected else None

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "has_chain": bool(chain),
        "chain_keys": list(chain.keys()) if isinstance(chain, dict) else None,
        "chain_preview": chain,
    }
@router.get("/api/test-spx-chain-shape")
def test_spx_chain_shape():
    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return {"error": "No chain"}

    item = chain["items"][0]
    expiration = item["expirations"][0]
    strike = expiration["strikes"][0]

    return {
        "item_keys": list(item.keys()),
        "expiration_keys": list(expiration.keys()),
        "strike_keys": list(strike.keys()),
        "first_expiration": {
            "expiration_type": expiration.get("expiration-type"),
            "expiration_date": expiration.get("expiration-date"),
            "days_to_expiration": expiration.get("days-to-expiration"),
            "settlement_type": expiration.get("settlement-type"),
        },
        "first_strike": strike,
    }


@router.get("/api/test-spx-option-quotes")
def test_spx_option_quotes():
    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return {"error": "No chain"}

    item = chain["items"][0]
    expiration = item["expirations"][0]
    strikes = expiration["strikes"]

    sample_symbols = []

    for strike in strikes:
        price = float(strike["strike-price"])

        if 7450 <= price <= 7625:
            sample_symbols.append(strike["put-streamer-symbol"])
            sample_symbols.append(strike["call-streamer-symbol"])

        if len(sample_symbols) >= 10:
            break

    quotes = tastytrade_api.get_option_quotes(sample_symbols)

    return {
        "using": "streamer-symbols",
        "sample_symbols": sample_symbols,
        "quote_count": len(quotes),
        "quotes": quotes,
        "status": tastytrade_api.get_status(),
    }


@router.get("/api/test-scanner-engine")
def test_scanner_engine():
    trade = find_best_iron_condor(
        spx_price=7535.54,
        expected_move=62.5,
        wing_width=25,
    )
@router.get("/api/test-candidates")
def test_candidates():
    candidates = generate_candidate_condors(
        spx_price=7535.54,
        expected_move=62.5,
        wing_width=25,
    )

    return {
        "count": len(candidates),
        "first": candidates[0] if candidates else None,
        "last": candidates[-1] if candidates else None,
    }
    return {
        "trade": trade,
    }
@router.get("/api/test-first-candidate-credit")
def test_first_candidate_credit():
    raw = generate_candidate_condors(
        spx_price=7535.54,
        expected_move=62.5,
        wing_width=25,
        days_to_expiration=1,
    )

    if not raw:
        return {"error": "No candidates"}

    trade = normalize_candidate(
        raw[-1],
        spx_price=7535.54,
        expected_move=62.5,
    )

    credit = calculate_iron_condor_credit(trade)

    return {
        "trade": trade,
        "credit": credit,
    }
@router.get("/api/test-expirations")
def test_expirations():
    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return {"error": "No chain"}

    item = chain["items"][0]

    return {
        "expirations": [
            {
                "date": exp.get("expiration-date"),
                "dte": exp.get("days-to-expiration"),
                "type": exp.get("expiration-type"),
                "settlement": exp.get("settlement-type"),
                "strike_count": len(exp.get("strikes", [])),
            }
            for exp in item.get("expirations", [])[:10]
        ]
    }
@router.get("/api/test-candidate-grid")
def test_candidate_grid():
    from bxk_app.option_scanner import generate_candidate_condors

    results = []

    for dte in [0, 1, 2, 3]:
        for wing in [5, 10, 20, 25]:
            candidates = generate_candidate_condors(
                spx_price=7535.54,
                expected_move=62.5,
                wing_width=wing,
                days_to_expiration=dte,
            )

            results.append({
                "dte": dte,
                "wing": wing,
                "count": len(candidates),
            })

    return {"results": results}
@router.get("/api/best-trade")
def best_trade():
    return build_best_trade(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )
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
@router.get("/api/strategy-rankings")
def strategy_rankings():
    return rank_strategies()