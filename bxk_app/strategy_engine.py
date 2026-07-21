"""
BXK Trader Pro

Strategy Engine

Purpose:
Compares live strategy results and selects the preferred strategy
based on trade quality, market permission, and Market DNA.
"""

from typing import Any


class StrategyEngine:
    """
    Selects the best available strategy from live strategy results.
    """

    STRATEGY_DNA_PREFERENCES = {
        "Balanced Auction": {
            "SPX Iron Condor": 12,
            "Iron Condor": 12,
            "Bull Put Credit Spread": 4,
            "Bear Call Credit Spread": 4,
        },
        "Calm Auction": {
            "SPX Iron Condor": 12,
            "Iron Condor": 12,
            "Bull Put Credit Spread": 5,
            "Bear Call Credit Spread": 5,
        },
        "Bullish Auction": {
            "Bull Put Credit Spread": 15,
            "SPX Iron Condor": 3,
            "Iron Condor": 3,
            "Bear Call Credit Spread": -12,
        },
        "Bearish Auction": {
            "Bear Call Credit Spread": 15,
            "SPX Iron Condor": 3,
            "Iron Condor": 3,
            "Bull Put Credit Spread": -12,
        },
        "Volatile Auction": {
            "SPX Iron Condor": -8,
            "Iron Condor": -8,
            "Bull Put Credit Spread": -5,
            "Bear Call Credit Spread": -5,
        },
        "High Stress": {
            "SPX Iron Condor": -15,
            "Iron Condor": -15,
            "Bull Put Credit Spread": -12,
            "Bear Call Credit Spread": -12,
        },
    }

    MARKET_PERMISSION_RANK = {
        "ENTER TRADE": 3,
        "TRADE": 3,
        "TRADE SMALL": 2,
        "WAIT": 1,
        "NO TRADE": 0,
    }

    def run(
        self,
        market_snapshot: dict[str, Any],
        market_dna: dict[str, Any],
        trade_quality: dict[str, Any],
        strategy_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Compare live strategy results and return the preferred strategy.

        strategy_results should contain builder responses such as:

        {
            "status": "OK",
            "best_trade": {
                "strategy": "Bull Put Credit Spread",
                "trade_score": 81,
                "final_decision": "NO TRADE",
                ...
            }
        }
        """

        dna = market_dna.get(
            "classification",
            "Unknown",
        )

        market_score = self._safe_float(
            trade_quality.get(
                "score",
                0,
            )
        )

        if not strategy_results:
            return self._fallback_selection(
                dna=dna,
                market_score=market_score,
            )

        ranked_strategies = []

        for result in strategy_results:
            ranked_trade = self._rank_strategy_result(
                result=result,
                dna=dna,
            )

            if ranked_trade is not None:
                ranked_strategies.append(
                    ranked_trade
                )

        if not ranked_strategies:
            return {
                "strategy": "None",
                "reason": (
                    "No live strategy returned a qualifying trade"
                ),
                "market_dna": dna,
                "market_score": market_score,
                "best_trade": None,
                "ranked_strategies": [],
            }

        ranked_strategies.sort(
            key=self._strategy_sort_key,
            reverse=True,
        )

        best = ranked_strategies[0]

        final_decision = best.get(
            "final_decision",
            "NO TRADE",
        )

        if final_decision in {
            "ENTER TRADE",
            "TRADE",
        }:
            reason = (
                f"{best['strategy']} has the highest "
                f"approved strategy score"
            )

        elif final_decision == "TRADE SMALL":
            reason = (
                f"{best['strategy']} ranks highest, "
                "but market conditions support reduced size"
            )

        elif final_decision == "WAIT":
            reason = (
                f"{best['strategy']} ranks highest, "
                "but market permission remains WAIT"
            )

        else:
            reason = (
                f"{best['strategy']} is the strongest "
                "available setup, but entry is not approved"
            )

        return {
            "strategy": best["strategy"],
            "reason": reason,
            "market_dna": dna,
            "market_score": market_score,
            "final_decision": final_decision,
            "best_trade": best,
            "ranked_strategies": ranked_strategies,
        }

    def _rank_strategy_result(
        self,
        result: dict[str, Any],
        dna: str,
    ) -> dict[str, Any] | None:
        """
        Convert a strategy builder response into a ranked trade.
        """

        if not isinstance(result, dict):
            return None

        if result.get("status") not in {
            "OK",
            "DEMO",
        }:
            return None

        trade = result.get(
            "best_trade"
        )

        if not isinstance(trade, dict):
            return None

        strategy_name = trade.get(
            "strategy",
            "Unknown Strategy",
        )

        trade_score = self._safe_float(
            trade.get(
                "trade_score",
                trade.get(
                    "trade_quality_score",
                    0,
                ),
            )
        )

        final_decision = trade.get(
            "final_decision",
            trade.get(
                "market_permission",
                "NO TRADE",
            ),
        )

        dna_adjustment = (
            self.STRATEGY_DNA_PREFERENCES
            .get(
                dna,
                {},
            )
            .get(
                strategy_name,
                0,
            )
        )

        permission_rank = (
            self.MARKET_PERMISSION_RANK.get(
                final_decision,
                0,
            )
        )

        selection_score = round(
            trade_score
            + dna_adjustment,
            2,
        )

        ranked_trade = dict(
            trade
        )

        ranked_trade.update(
            {
                "strategy": strategy_name,
                "base_trade_score": trade_score,
                "dna_adjustment": dna_adjustment,
                "selection_score": selection_score,
                "permission_rank": permission_rank,
                "final_decision": final_decision,
                "source_status": result.get(
                    "status"
                ),
            }
        )

        return ranked_trade

    def _strategy_sort_key(
        self,
        trade: dict[str, Any],
    ) -> tuple[int, float]:
        """
        Rank approved trades first, then rank by selection score.
        """

        return (
            int(
                trade.get(
                    "permission_rank",
                    0,
                )
            ),
            self._safe_float(
                trade.get(
                    "selection_score",
                    0,
                )
            ),
        )

    def _fallback_selection(
        self,
        dna: str,
        market_score: float,
    ) -> dict[str, Any]:
        """
        Preserve the old selector behavior when no live strategy
        results are supplied.
        """

        if market_score < 70:
            strategy = "None"
            reason = "Trade quality too low"

        elif dna in {
            "Balanced Auction",
            "Calm Auction",
        }:
            strategy = "Iron Condor"
            reason = "Market favors neutral premium selling"

        elif dna == "Bullish Auction":
            strategy = "Bull Put Credit Spread"
            reason = "Market favors bullish premium selling"

        elif dna == "Bearish Auction":
            strategy = "Bear Call Credit Spread"
            reason = "Market favors bearish premium selling"

        elif dna in {
            "Volatile Auction",
            "High Stress",
        }:
            strategy = "Directional"
            reason = "Volatility is elevated"

        else:
            strategy = "Monitor"
            reason = "Market DNA is unclear"

        return {
            "strategy": strategy,
            "reason": reason,
            "market_dna": dna,
            "market_score": market_score,
            "best_trade": None,
            "ranked_strategies": [],
        }

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            return float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return default