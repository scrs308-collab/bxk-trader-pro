from datetime import datetime

from bxk_app.market_engine import MarketEngine
from bxk_app.opportunity_engine import build_opportunity
from bxk_app.scoring import run_trade_quality
from bxk_app.strategy_ranker import rank_strategies
from bxk_app.trade_builder import build_best_trade

def safe_market_value(
    market,
    field_name,
    default=None,
):
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

def get_recommendation():
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