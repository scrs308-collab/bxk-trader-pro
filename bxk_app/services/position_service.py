import os
import threading
import time

from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.brokers.tastytrade import (
    broker as order_broker,
)
from bxk_app.market_data import market_data
from bxk_app.market_engine import market_engine
from bxk_app.position_monitor import (
    build_position_summaries,
)
from bxk_app.services.execution_audit import (
    read_recent_submitted_orders,
)
from bxk_app.services.trade_journal_service import (
    observe_linked_positions,
    reconcile_missing_trade_journals,
)


_DEFAULT_JOURNAL_RECONCILE_SECONDS = 60
_MIN_JOURNAL_RECONCILE_SECONDS = 30
_MAX_JOURNAL_RECONCILE_SECONDS = 3600

_JOURNAL_RECONCILE_LOCK = threading.Lock()
_JOURNAL_RECONCILE_NEXT_AT = 0.0


def _journal_reconcile_interval_seconds():
    raw = os.getenv(
        "BXK_TRADE_JOURNAL_RECONCILE_SECONDS",
        str(
            _DEFAULT_JOURNAL_RECONCILE_SECONDS
        ),
    )

    try:
        value = int(raw)

    except (
        TypeError,
        ValueError,
    ):
        value = (
            _DEFAULT_JOURNAL_RECONCILE_SECONDS
        )

    return max(
        _MIN_JOURNAL_RECONCILE_SECONDS,
        min(
            value,
            _MAX_JOURNAL_RECONCILE_SECONDS,
        ),
    )


def _reconcile_trade_journal_closures(
    positions,
    *,
    broker_client=None,
    now_monotonic=None,
):
    """
    Throttled, failure-isolated closing-order check.

    Position Monitor must remain healthy even if
    order-history reconciliation fails.
    """

    global _JOURNAL_RECONCILE_NEXT_AT

    now_value = (
        time.monotonic()
        if now_monotonic is None
        else float(
            now_monotonic
        )
    )

    with _JOURNAL_RECONCILE_LOCK:
        if (
            now_value
            < _JOURNAL_RECONCILE_NEXT_AT
        ):
            return {
                "checked": False,
                "reason": "THROTTLED",
                "results": [],
            }

        _JOURNAL_RECONCILE_NEXT_AT = (
            now_value
            + _journal_reconcile_interval_seconds()
        )

    try:
        return reconcile_missing_trade_journals(
            positions,
            broker_client=(
                broker_client
                or order_broker
            ),
        )

    except Exception as exc:
        return {
            "checked": False,
            "reason":
                "JOURNAL_RECONCILIATION_FAILED",
            "error":
                type(exc).__name__,
            "results": [],
        }



def _leg_symbols(item: dict) -> frozenset[str]:
    return frozenset(
        str(leg.get("symbol") or "").strip()
        for leg in (item.get("legs") or [])
        if str(leg.get("symbol") or "").strip()
    )


def link_positions_to_submissions(
    summaries: list[dict],
    submissions: list[dict],
) -> list[dict]:
    """Link open positions to exact audited broker orders."""

    available_submissions = list(submissions or [])
    linked = []

    for summary in summaries or []:
        enriched = dict(summary)
        position_symbols = _leg_symbols(summary)
        match_index = None

        if len(position_symbols) == 4:
            for index, submission in enumerate(
                available_submissions
            ):
                order = submission.get("order") or {}

                if _leg_symbols(order) == position_symbols:
                    match_index = index
                    break

        if match_index is not None:
            submission = available_submissions.pop(
                match_index
            )
            order = submission.get("order") or {}
            enriched.update({
                "broker_linked": True,
                "broker_order_id": submission.get(
                    "order_id"
                ),
                "submitted_at": submission.get(
                    "timestamp_utc"
                ),
                "submitted_limit_credit": order.get(
                    "limit_price",
                    order.get("credit"),
                ),
            })
        else:
            enriched["broker_linked"] = False

        linked.append(enriched)

    return linked


def get_position_monitor():
    """
    Return open SPX option legs grouped into separate
    Iron Condor position summaries.
    """

    try:

        connected = tastytrade_api.authenticate()

        positions = (
            tastytrade_api.get_position_summary()
            if connected
            else []
        )

        if not positions:
            if connected:
                _reconcile_trade_journal_closures(
                    []
                )

            return {
                "status": "EMPTY",
                "connected": connected,
                "position": None,
                "positions": [],
                "position_count": 0,
                "total_open_pnl": 0.0,
                "message": (
                    "No open positions found."
                ),
            }

        snapshot = (
            market_data.get_snapshot()
        )

        spx_price = (
            (snapshot or {}).get("spx")
            or (snapshot or {}).get(
                "spx_price"
            )
            or (snapshot or {}).get(
                "price"
            )
        )

        if not spx_price:
            try:
                live_market = (
                    market_engine.update()
                )

                if isinstance(
                    live_market,
                    dict,
                ):
                    spx_price = (
                        live_market.get("spx")
                        or live_market.get(
                            "spx_price"
                        )
                        or live_market.get(
                            "price"
                        )
                    )

            except Exception:
                spx_price = None

        try:
            spx_price = float(
                spx_price
            )

        except (
            TypeError,
            ValueError,
        ):
            spx_price = None

        if (
            spx_price is not None
            and spx_price <= 0
        ):
            spx_price = None

        summaries = (
            build_position_summaries(
                positions=positions,
                spx_price=spx_price,
            )
        )

        summaries = link_positions_to_submissions(
            summaries,
            read_recent_submitted_orders(),
        )

        # Journal observation is deliberately
        # downstream of live position construction.
        # It must never block Position Monitor.
        try:
            observe_linked_positions(
                summaries
            )
        except Exception:
            pass

        _reconcile_trade_journal_closures(
            summaries
        )

        if not summaries:
            _reconcile_trade_journal_closures(
                []
            )

            return {
                "status": "UNSUPPORTED",
                "connected": connected,
                "position": None,
                "positions": [],
                "position_count": 0,
                "total_open_pnl": 0.0,
                "leg_count": len(
                    positions
                ),
                "message": (
                    "Open positions could not "
                    "be grouped into supported "
                    "Iron Condor positions."
                ),
            }

        total_open_pnl = round(
            sum(
                float(
                    summary.get(
                        "pnl",
                        0,
                    )
                    or 0
                )
                for summary in summaries
            ),
            2,
        )

        return {
            "status": "OK",
            "connected": connected,

            # Keep this temporarily so the existing
            # dashboard does not break before the UI
            # is updated for multiple cards.
            "position": summaries[0],

            # New multi-position payload.
            "positions": summaries,
            "position_count": len(
                summaries
            ),
            "total_open_pnl": (
                total_open_pnl
            ),
        }

    except Exception as error:
        return {
            "status": "ERROR",
            "connected": False,
            "position": None,
            "positions": [],
            "position_count": 0,
            "total_open_pnl": 0.0,
            "message": str(error),
        }
