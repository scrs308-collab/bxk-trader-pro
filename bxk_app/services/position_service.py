import os
import threading
import time

from bxk_app.overnight_carry_risk import (
    calculate_overnight_carry_risk,
)
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
    get_open_trade_journal_candidates,
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



def _invoke_reconcile_missing_trade_journals(
    positions,
    *,
    broker_client,
    user_context=None,
):
    if user_context is None:
        return reconcile_missing_trade_journals(
            positions,
            broker_client=broker_client,
        )

    return reconcile_missing_trade_journals(
        positions,
        broker_client=broker_client,
        user_context=user_context,
    )


def _reconcile_trade_journal_closures(
    positions,
    *,
    broker_client=None,
    now_monotonic=None,
    user_context=None,
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
        return _invoke_reconcile_missing_trade_journals(
            positions,
            broker_client=(
                broker_client
                or order_broker
            ),
            user_context=
                user_context,
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
                "broker_link_source":
                    "EXECUTION_AUDIT",
            })
        else:
            enriched["broker_linked"] = False

        linked.append(enriched)

    return linked



def _journal_candidate_symbols(
    candidate: dict,
) -> frozenset[str]:
    return frozenset(
        str(symbol or "").strip()
        for symbol in (
            candidate.get("symbols")
            or []
        )
        if str(symbol or "").strip()
    )


def link_positions_to_journals(
    summaries: list[dict],
    candidates: list[dict],
) -> list[dict]:
    """
    Fallback-link unmatched live positions to exactly
    one OPEN/SUBMITTED TradeJournal row by exact
    four-leg option-symbol identity.
    """

    available = list(candidates or [])
    linked = []

    for summary in summaries or []:
        enriched = dict(summary)

        if enriched.get("broker_linked"):
            linked.append(enriched)
            continue

        position_symbols = _leg_symbols(summary)
        matches = []

        if len(position_symbols) == 4:
            for index, candidate in enumerate(
                available
            ):
                if (
                    _journal_candidate_symbols(
                        candidate
                    )
                    == position_symbols
                ):
                    matches.append(index)

        if len(matches) == 1:
            candidate = available.pop(
                matches[0]
            )

            enriched.update({
                "broker_linked":
                    True,
                "broker_order_id":
                    candidate.get(
                        "broker_order_id"
                    ),
                "submitted_at":
                    candidate.get(
                        "submitted_at"
                    ),
                "submitted_limit_credit":
                    candidate.get(
                        "submitted_limit_credit"
                    ),
                "broker_link_source":
                    "TRADE_JOURNAL",
            })

        linked.append(enriched)

    return linked


def _carry_positive_float(value):
    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if number <= 0:
        return None

    return number


def _attach_provisional_carry_risk(
    summaries,
    *,
    snapshot,
    spx_price,
):
    """
    Attach a live, observation-only overnight carry
    evaluation to Position Monitor summaries.

    This is deliberately provisional. The official
    close snapshot remains owned by the overnight
    carry learning / journal workflow.
    """

    market_snapshot = snapshot or {}

    expected_move = _carry_positive_float(
        market_snapshot.get(
            "expected_move"
        )
    )

    vix1d = _carry_positive_float(
        market_snapshot.get(
            "vix1d"
        )
    )

    vix = _carry_positive_float(
        market_snapshot.get(
            "vix"
        )
    )

    if vix1d is not None:
        expected_move_source = "VIX1D"

    elif vix is not None:
        expected_move_source = "VIX"

    else:
        expected_move_source = None

    evaluated_at = (
        market_snapshot.get(
            "timestamp"
        )
    )

    for summary in summaries:
        try:
            carry_risk = (
                calculate_overnight_carry_risk(
                    spx_close=spx_price,
                    short_put=summary.get(
                        "sell_put"
                    ),
                    short_call=summary.get(
                        "sell_call"
                    ),
                    expected_move=expected_move,
                    expected_move_source=(
                        expected_move_source
                    ),
                    dte=summary.get(
                        "dte"
                    ),
                )
            )

        except Exception:
            carry_risk = {
                "available": False,
                "observation_only": True,
                "execution_authorized": False,
                "state": "UNKNOWN",
                "decision": "UNAVAILABLE",
                "recommendation": None,
                "reason_code": (
                    "LIVE_CARRY_EVALUATION_ERROR"
                ),
            }

        if not isinstance(
            carry_risk,
            dict,
        ):
            carry_risk = {
                "available": False,
                "observation_only": True,
                "execution_authorized": False,
                "state": "UNKNOWN",
                "decision": "UNAVAILABLE",
                "recommendation": None,
                "reason_code": (
                    "LIVE_CARRY_EVALUATION_INVALID"
                ),
            }

        carry_risk = dict(
            carry_risk
        )

        carry_risk[
            "evaluation_phase"
        ] = "PROVISIONAL"

        carry_risk[
            "evaluated_at"
        ] = evaluated_at

        summary[
            "carry_risk"
        ] = carry_risk

    return summaries




def _invoke_position_reconcile(
    positions,
    *,
    broker_client=None,
    user_context=None,
):
    if user_context is None:
        return _reconcile_trade_journal_closures(
            positions
        )

    return _reconcile_trade_journal_closures(
        positions,
        broker_client=broker_client,
        user_context=user_context,
    )


def _get_open_journal_candidates_for_context(
    *,
    user_context=None,
):
    if user_context is None:
        return get_open_trade_journal_candidates()

    return get_open_trade_journal_candidates(
        user_context=user_context,
    )


def _observe_linked_positions_for_context(
    positions,
    *,
    user_context=None,
):
    if user_context is None:
        return observe_linked_positions(
            positions
        )

    return observe_linked_positions(
        positions,
        user_context=user_context,
    )


def get_position_monitor(
    *,
    broker_client=None,
    user_context=None,
):
    """
    Return open SPX option legs grouped into separate
    Iron Condor position summaries.
    """

    try:

        active_broker = (
            broker_client
            or tastytrade_api
        )

        connected = (
            active_broker.authenticate()
        )

        positions = (
            active_broker
            .get_position_summary()
            if connected
            else []
        )

        if not positions:
            if connected:
                _invoke_position_reconcile(
                    [],
                    broker_client=(
                        broker_client
                        or order_broker
                    ),
                    user_context=
                        user_context,
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

        carry_snapshot = (
            market_data.get_snapshot()
        )

        summaries = (
            _attach_provisional_carry_risk(
                summaries,
                snapshot=carry_snapshot,
                spx_price=spx_price,
            )
        )

        role = str(
            (
                user_context
                or {}
            ).get(
                "role"
            )
            or ""
        ).strip().upper()

        # The execution audit is currently one global
        # OWNER file. Until it becomes user-scoped,
        # non-OWNER users must never read/link against it.
        if (
            user_context is None
            or role == "OWNER"
        ):
            summaries = (
                link_positions_to_submissions(
                    summaries,
                    read_recent_submitted_orders(),
                )
            )

        try:
            journal_candidates = (
                _get_open_journal_candidates_for_context(
                    user_context=
                        user_context,
                )
            )
        except Exception:
            journal_candidates = []

        summaries = link_positions_to_journals(
            summaries,
            journal_candidates,
        )

        # Journal observation is deliberately
        # downstream of live position construction.
        # It must never block Position Monitor.
        try:
            _observe_linked_positions_for_context(
                summaries,
                user_context=
                    user_context,
            )
        except Exception:
            pass

        _invoke_position_reconcile(
            summaries,
            broker_client=(
                broker_client
                or order_broker
            ),
            user_context=
                user_context,
        )

        if not summaries:
            _invoke_position_reconcile(
                [],
                broker_client=(
                    broker_client
                    or order_broker
                ),
                user_context=
                    user_context,
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
