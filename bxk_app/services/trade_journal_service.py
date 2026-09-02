import json
import uuid
from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import select

from bxk_app.database import (
    database_configured,
    get_session_factory,
)
from bxk_app.db_models.trade_journal import (
    TradeJournal,
)
from bxk_app.services.position_threat_service import (
    STATE_RANK,
    classify_position_threat,
)


_STATUS_RANK = {
    "SUBMITTED": 0,
    "OPEN": 1,
    "CLOSED": 2,
}


def _number(value):
    try:
        if value is None:
            return None

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _integer(value):
    try:
        if value is None:
            return None

        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _date(value):
    if isinstance(value, date):
        return value

    if value is None:
        return None

    try:
        return date.fromisoformat(
            str(value)[:10]
        )

    except ValueError:
        return None


def _datetime(value):
    if isinstance(value, datetime):
        result = value

    elif value:
        text = str(value).strip()

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        try:
            result = (
                datetime.fromisoformat(
                    text
                )
            )
        except ValueError:
            return None

    else:
        return None

    if result.tzinfo is None:
        result = result.replace(
            tzinfo=timezone.utc
        )

    return result


def _user_id(context):
    if not isinstance(context, dict):
        return None

    value = context.get("user_id")

    if value is None:
        return None

    if isinstance(value, uuid.UUID):
        return value

    try:
        return uuid.UUID(
            str(value)
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
    ):
        return None


def _json_safe(value):
    try:
        return json.loads(
            json.dumps(
                value,
                default=str,
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _extract_strikes(
    order: dict,
):
    result = {
        "short_put": None,
        "long_put": None,
        "short_call": None,
        "long_call": None,
    }

    for leg in (
        order.get("legs") or []
    ):
        if not isinstance(
            leg,
            dict,
        ):
            continue

        action = str(
            leg.get("action") or ""
        ).strip().upper()

        option_type = str(
            leg.get("option_type")
            or leg.get("option-type")
            or ""
        ).strip().upper()

        strike = _number(
            leg.get("strike")
        )

        if strike is None:
            continue

        if (
            action == "SELL"
            and option_type == "PUT"
        ):
            result["short_put"] = strike

        elif (
            action == "BUY"
            and option_type == "PUT"
        ):
            result["long_put"] = strike

        elif (
            action == "SELL"
            and option_type == "CALL"
        ):
            result["short_call"] = strike

        elif (
            action == "BUY"
            and option_type == "CALL"
        ):
            result["long_call"] = strike

    return result


def _journal_status(
    broker_status,
    reconciliation,
):
    status = str(
        broker_status or ""
    ).strip().upper()

    reconciliation = (
        reconciliation
        if isinstance(
            reconciliation,
            dict,
        )
        else {}
    )

    filled_quantity = _number(
        reconciliation.get(
            "filled_quantity"
        )
    )

    fill_price = _number(
        reconciliation.get(
            "average_fill_price"
        )
    )

    if (
        status == "FILLED"
        or (
            filled_quantity is not None
            and filled_quantity > 0
        )
        or fill_price is not None
    ):
        return "OPEN"

    return "SUBMITTED"


def record_submitted_trade(
    *,
    user_context=None,
    broker_order_id,
    broker_status=None,
    order=None,
    trade=None,
    broker_order=None,
    reconciliation=None,
    session_factory=None,
):
    """
    Persist one confirmed BXK submission.

    Idempotent on broker_order_id.

    Journal persistence must never be used as
    evidence that broker submission succeeded.
    The broker remains the source of truth.
    """

    if not database_configured():
        return {
            "recorded": False,
            "reason":
                "DATABASE_NOT_CONFIGURED",
        }

    clean_order_id = str(
        broker_order_id or ""
    ).strip()

    if not clean_order_id:
        raise ValueError(
            "Broker order ID is required."
        )

    order = (
        order
        if isinstance(order, dict)
        else {}
    )

    trade = (
        trade
        if isinstance(trade, dict)
        else {}
    )

    broker_order = (
        broker_order
        if isinstance(
            broker_order,
            dict,
        )
        else {}
    )

    reconciliation = (
        reconciliation
        if isinstance(
            reconciliation,
            dict,
        )
        else {}
    )

    strikes = _extract_strikes(
        order
    )

    fill_credit = _number(
        reconciliation.get(
            "average_fill_price"
        )
    )

    submitted_at = (
        _datetime(
            broker_order.get(
                "received-at"
            )
        )
        or _datetime(
            broker_order.get(
                "created-at"
            )
        )
        or _datetime(
            reconciliation.get(
                "updated_at"
            )
        )
        or datetime.now(
            timezone.utc
        )
    )

    incoming_status = (
        _journal_status(
            broker_status,
            reconciliation,
        )
    )

    snapshot = _json_safe({
        "trade": trade,
        "order": order,
        "broker_status":
            broker_status,
        "reconciliation":
            reconciliation,
    })

    factory = (
        session_factory
        or get_session_factory()
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            ).where(
                TradeJournal.broker_order_id
                == clean_order_id
            )
        ).scalar_one_or_none()

        created = journal is None

        if journal is None:
            journal = TradeJournal(
                broker_order_id=
                    clean_order_id,
                status=incoming_status,
            )

            session.add(journal)

        parsed_user_id = _user_id(
            user_context
        )

        if parsed_user_id is not None:
            journal.user_id = (
                parsed_user_id
            )

        current_status = str(
            journal.status or ""
        ).strip().upper()

        if (
            _STATUS_RANK.get(
                incoming_status,
                0,
            )
            >= _STATUS_RANK.get(
                current_status,
                -1,
            )
        ):
            journal.status = (
                incoming_status
            )

        journal.broker_status = (
            str(
                broker_status
                or ""
            ).strip()
            or None
        )

        journal.strategy = (
            str(
                order.get("strategy")
                or trade.get("strategy")
                or ""
            ).strip()
            or None
        )

        journal.underlying = (
            str(
                order.get("symbol")
                or trade.get("symbol")
                or "SPX"
            ).strip().upper()
            or "SPX"
        )

        journal.expiration = _date(
            order.get("expiration")
            or trade.get(
                "expiration"
            )
        )

        journal.dte = _integer(
            order.get("dte")
            if order.get("dte")
            is not None
            else trade.get("dte")
        )

        journal.quantity = _integer(
            order.get("quantity")
        )

        journal.wing_width = _number(
            order.get("wing_width")
            if order.get("wing_width")
            is not None
            else trade.get(
                "wing_width"
            )
        )

        for field, value in (
            strikes.items()
        ):
            setattr(
                journal,
                field,
                value,
            )

        journal.submitted_credit = (
            _number(
                order.get(
                    "limit_price"
                )
            )
            or _number(
                order.get("credit")
            )
        )

        if fill_credit is not None:
            journal.entry_fill_credit = (
                fill_credit
            )

        journal.max_profit = _number(
            order.get("max_profit")
            if order.get("max_profit")
            is not None
            else trade.get(
                "max_profit"
            )
        )

        journal.max_risk = _number(
            order.get("max_risk")
            if order.get("max_risk")
            is not None
            else trade.get(
                "max_risk"
            )
        )

        if journal.submitted_at is None:
            journal.submitted_at = (
                submitted_at
            )

        if (
            journal.status == "OPEN"
            and journal.opened_at is None
        ):
            journal.opened_at = (
                submitted_at
            )

        journal.entry_snapshot = (
            snapshot
        )

        session.commit()
        session.refresh(journal)

        return {
            "recorded": True,
            "created": created,
            "journal_id":
                str(journal.id),
            "broker_order_id":
                journal.broker_order_id,
            "status":
                journal.status,
        }


_TERMINAL_JOURNAL_STATUSES = {
    "CLOSED",
    "EXPIRED",
    "CANCELLED",
    "CANCELED",
}


def observe_open_position(
    position: dict,
    *,
    observed_at=None,
    session_factory=None,
):
    """
    Preserve meaningful live extremes for a linked
    open BXK position.

    This function never creates a journal row.
    The confirmed broker submission is responsible
    for journal creation.
    """

    if not database_configured():
        return {
            "recorded": False,
            "reason":
                "DATABASE_NOT_CONFIGURED",
        }

    if not isinstance(
        position,
        dict,
    ):
        return {
            "recorded": False,
            "reason":
                "INVALID_POSITION",
        }

    broker_order_id = str(
        position.get(
            "broker_order_id"
        )
        or ""
    ).strip()

    if not broker_order_id:
        return {
            "recorded": False,
            "reason":
                "BROKER_ORDER_ID_MISSING",
        }

    timestamp = (
        _datetime(observed_at)
        if observed_at is not None
        else datetime.now(
            timezone.utc
        )
    )

    if timestamp is None:
        timestamp = datetime.now(
            timezone.utc
        )

    risk = classify_position_threat(
        position
    )

    pnl = _number(
        position.get("pnl")
    )

    pnl_is_estimate = bool(
        position.get(
            "pnl_is_estimate",
            False,
        )
    )

    factory = (
        session_factory
        or get_session_factory()
    )

    with factory() as session:
        statement = (
            select(
                TradeJournal
            )
            .where(
                TradeJournal.broker_order_id
                == broker_order_id
            )
            .with_for_update()
        )

        journal = session.execute(
            statement
        ).scalar_one_or_none()

        if journal is None:
            return {
                "recorded": False,
                "reason":
                    "JOURNAL_NOT_FOUND",
                "broker_order_id":
                    broker_order_id,
            }

        existing_status = str(
            journal.status or ""
        ).strip().upper()

        if (
            existing_status
            in _TERMINAL_JOURNAL_STATUSES
        ):
            return {
                "recorded": False,
                "reason":
                    "JOURNAL_TERMINAL",
                "broker_order_id":
                    broker_order_id,
                "status":
                    existing_status,
            }

        changed = False

        if journal.status != "OPEN":
            journal.status = "OPEN"
            changed = True

        if journal.opened_at is None:
            journal.opened_at = timestamp
            changed = True

        pnl_recorded = False

        # Quote-quality guard:
        # estimated P/L does not become learning data.
        if (
            pnl is not None
            and not pnl_is_estimate
        ):
            pnl_recorded = True

            if (
                journal.best_open_pnl
                is None
                or pnl
                > journal.best_open_pnl
            ):
                journal.best_open_pnl = pnl
                changed = True

            if (
                journal.worst_open_pnl
                is None
                or pnl
                < journal.worst_open_pnl
            ):
                journal.worst_open_pnl = pnl
                changed = True

        if risk is not None:
            distance = _number(
                risk.get("distance")
            )

            current_state = str(
                risk.get("state")
                or ""
            ).strip().upper()

            if (
                distance is not None
                and (
                    journal.min_short_cushion
                    is None
                    or distance
                    < journal.min_short_cushion
                )
            ):
                journal.min_short_cushion = (
                    distance
                )
                changed = True

            if current_state in STATE_RANK:
                stored_state = str(
                    journal.worst_threat_state
                    or ""
                ).strip().upper()

                if (
                    stored_state
                    not in STATE_RANK
                    or STATE_RANK[
                        current_state
                    ]
                    > STATE_RANK[
                        stored_state
                    ]
                ):
                    journal.worst_threat_state = (
                        current_state
                    )
                    changed = True

                current_rank = STATE_RANK[
                    current_state
                ]

                thresholds = (
                    (
                        "ORANGE",
                        "first_orange_at",
                    ),
                    (
                        "RED",
                        "first_red_at",
                    ),
                    (
                        "CRITICAL",
                        "first_critical_at",
                    ),
                )

                for (
                    threshold,
                    field,
                ) in thresholds:
                    if (
                        current_rank
                        >= STATE_RANK[
                            threshold
                        ]
                        and getattr(
                            journal,
                            field,
                        )
                        is None
                    ):
                        setattr(
                            journal,
                            field,
                            timestamp,
                        )
                        changed = True

        if changed:
            session.commit()
            session.refresh(
                journal
            )

        return {
            "recorded": True,
            "changed": changed,
            "broker_order_id":
                broker_order_id,
            "status":
                journal.status,
            "pnl_recorded":
                pnl_recorded,
            "best_open_pnl":
                journal.best_open_pnl,
            "worst_open_pnl":
                journal.worst_open_pnl,
            "min_short_cushion":
                journal.min_short_cushion,
            "worst_threat_state":
                journal.worst_threat_state,
        }


def observe_linked_positions(
    positions,
    *,
    observed_at=None,
    session_factory=None,
):
    """
    Observe every broker-linked position independently.

    One journal failure must never prevent Position
    Monitor or another position from being processed.
    """

    results = []

    if not database_configured():
        return results

    for position in (
        positions or []
    ):
        if not isinstance(
            position,
            dict,
        ):
            continue

        if not position.get(
            "broker_linked"
        ):
            continue

        if not position.get(
            "broker_order_id"
        ):
            continue

        try:
            result = (
                observe_open_position(
                    position,
                    observed_at=
                        observed_at,
                    session_factory=
                        session_factory,
                )
            )

        except Exception as exc:
            result = {
                "recorded": False,
                "reason":
                    "JOURNAL_OBSERVATION_FAILED",
                "broker_order_id":
                    position.get(
                        "broker_order_id"
                    ),
                "error":
                    type(exc).__name__,
            }

        results.append(
            result
        )

    return results


def _normalized_broker_action(
    value,
):
    return " ".join(
        str(value or "")
        .replace("-", " ")
        .strip()
        .upper()
        .split()
    )


def _entry_order_from_journal(
    journal,
):
    snapshot = (
        journal.entry_snapshot
        if isinstance(
            journal.entry_snapshot,
            dict,
        )
        else {}
    )

    order = snapshot.get(
        "order"
    )

    return (
        order
        if isinstance(
            order,
            dict,
        )
        else {}
    )


def _expected_close_actions(
    journal,
):
    entry_order = (
        _entry_order_from_journal(
            journal
        )
    )

    expected = {}

    for leg in (
        entry_order.get("legs")
        or []
    ):
        if not isinstance(
            leg,
            dict,
        ):
            return {}

        symbol = str(
            leg.get("symbol")
            or ""
        ).strip()

        action = str(
            leg.get("action")
            or ""
        ).strip().upper()

        if not symbol:
            return {}

        if action == "SELL":
            expected[
                symbol
            ] = "BUY TO CLOSE"

        elif action == "BUY":
            expected[
                symbol
            ] = "SELL TO CLOSE"

        else:
            return {}

    return expected


def _order_fill_timestamp(
    order,
):
    timestamps = []

    for leg in (
        (order or {}).get("legs")
        or []
    ):
        if not isinstance(
            leg,
            dict,
        ):
            continue

        for fill in (
            leg.get("fills")
            or []
        ):
            if not isinstance(
                fill,
                dict,
            ):
                continue

            timestamp = _datetime(
                fill.get(
                    "filled-at"
                )
            )

            if timestamp is not None:
                timestamps.append(
                    timestamp
                )

    if timestamps:
        return max(
            timestamps
        )

    for field in (
        "terminal-at",
        "updated-at",
        "received-at",
        "created-at",
    ):
        timestamp = _datetime(
            (order or {}).get(
                field
            )
        )

        if timestamp is not None:
            return timestamp

    return None


def _order_net_value(
    order,
):
    """
    Return signed strategy price per spread.

    Debit is positive.
    Credit is negative.
    """

    if not isinstance(
        order,
        dict,
    ):
        return None

    direct_price = None

    for field in (
        "average-fill-price",
        "average-price",
        "fill-price",
    ):
        direct_price = _number(
            order.get(field)
        )

        if direct_price is not None:
            break

    if direct_price is not None:
        effect = str(
            order.get(
                "price-effect"
            )
            or order.get(
                "value-effect"
            )
            or ""
        ).strip().upper()

        if effect == "CREDIT":
            return -abs(
                direct_price
            )

        if effect == "DEBIT":
            return abs(
                direct_price
            )

    signed_total = 0.0
    saw_fill = False

    for leg in (
        order.get("legs")
        or []
    ):
        if not isinstance(
            leg,
            dict,
        ):
            return None

        fills = (
            leg.get("fills")
            or []
        )

        if not fills:
            return None

        value_total = 0.0
        quantity_total = 0.0

        for fill in fills:
            if not isinstance(
                fill,
                dict,
            ):
                continue

            price = _number(
                fill.get(
                    "fill-price"
                )
            )

            quantity = _number(
                fill.get(
                    "quantity"
                )
            )

            if (
                price is None
                or quantity is None
                or quantity <= 0
            ):
                continue

            value_total += (
                price * quantity
            )

            quantity_total += (
                quantity
            )

        if quantity_total <= 0:
            return None

        saw_fill = True

        average = (
            value_total
            / quantity_total
        )

        action = (
            _normalized_broker_action(
                leg.get(
                    "action"
                )
            )
        )

        if action.startswith(
            "BUY "
        ):
            signed_total += (
                average
            )

        elif action.startswith(
            "SELL "
        ):
            signed_total -= (
                average
            )

        else:
            return None

    if not saw_fill:
        return None

    return round(
        signed_total,
        6,
    )


def _opening_fill_credit(
    order,
):
    value = _order_net_value(
        order
    )

    if value is None:
        return None

    return abs(
        value
    )


def _closing_exit_debit(
    order,
):
    return _order_net_value(
        order
    )


def _closing_order_matches(
    journal,
    order,
):
    if not isinstance(
        order,
        dict,
    ):
        return False

    opening_order_id = str(
        journal.broker_order_id
        or ""
    ).strip()

    closing_order_id = str(
        order.get("id")
        or ""
    ).strip()

    if (
        not closing_order_id
        or closing_order_id
        == opening_order_id
    ):
        return False

    status = str(
        order.get("status")
        or ""
    ).strip().upper()

    if status != "FILLED":
        return False

    expected = (
        _expected_close_actions(
            journal
        )
    )

    if not expected:
        return False

    actual = {}

    for leg in (
        order.get("legs")
        or []
    ):
        if not isinstance(
            leg,
            dict,
        ):
            return False

        symbol = str(
            leg.get("symbol")
            or ""
        ).strip()

        action = (
            _normalized_broker_action(
                leg.get(
                    "action"
                )
            )
        )

        if not symbol:
            return False

        actual[
            symbol
        ] = action

        quantity = _number(
            leg.get(
                "quantity"
            )
        )

        required_quantity = (
            journal.quantity
            or 1
        )

        if (
            quantity is None
            or quantity
            < required_quantity
        ):
            return False

    if (
        set(actual)
        != set(expected)
    ):
        return False

    return all(
        actual.get(symbol)
        == action
        for symbol, action
        in expected.items()
    )


def _trade_outcome(
    realized_pnl,
):
    pnl = _number(
        realized_pnl
    )

    if pnl is None:
        return None

    if pnl > 0.01:
        return "WIN"

    if pnl < -0.01:
        return "LOSS"

    return "SCRATCH"


def finalize_closed_trade(
    *,
    broker_order_id,
    closing_order,
    opening_order=None,
    session_factory=None,
):
    """
    Finalize one journal only from a confirmed,
    filled closing broker order.
    """

    if not database_configured():
        return {
            "recorded": False,
            "reason":
                "DATABASE_NOT_CONFIGURED",
        }

    clean_order_id = str(
        broker_order_id
        or ""
    ).strip()

    if not clean_order_id:
        return {
            "recorded": False,
            "reason":
                "BROKER_ORDER_ID_MISSING",
        }

    factory = (
        session_factory
        or get_session_factory()
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
            .where(
                TradeJournal.broker_order_id
                == clean_order_id
            )
            .with_for_update()
        ).scalar_one_or_none()

        if journal is None:
            return {
                "recorded": False,
                "reason":
                    "JOURNAL_NOT_FOUND",
            }

        if (
            journal.status == "CLOSED"
            and journal.
            closing_broker_order_id
        ):
            return {
                "recorded": True,
                "changed": False,
                "status": "CLOSED",
                "closing_broker_order_id":
                    journal.
                    closing_broker_order_id,
            }

        if not _closing_order_matches(
            journal,
            closing_order,
        ):
            return {
                "recorded": False,
                "reason":
                    "CLOSE_ORDER_MISMATCH",
            }

        closing_order_id = str(
            closing_order.get("id")
            or ""
        ).strip()

        entry_credit = (
            journal.entry_fill_credit
        )

        if (
            entry_credit is None
            and isinstance(
                opening_order,
                dict,
            )
        ):
            entry_credit = (
                _opening_fill_credit(
                    opening_order
                )
            )

            if entry_credit is not None:
                journal.entry_fill_credit = (
                    entry_credit
                )

        exit_debit = (
            _closing_exit_debit(
                closing_order
            )
        )

        quantity = int(
            journal.quantity
            or 1
        )

        realized_pnl = None

        if (
            entry_credit is not None
            and exit_debit is not None
        ):
            realized_pnl = round(
                (
                    entry_credit
                    - exit_debit
                )
                * 100
                * quantity,
                2,
            )

        closed_at = (
            _order_fill_timestamp(
                closing_order
            )
            or datetime.now(
                timezone.utc
            )
        )

        journal.status = "CLOSED"
        journal.broker_status = (
            str(
                closing_order.get(
                    "status"
                )
                or "FILLED"
            ).strip()
            or "FILLED"
        )

        journal.closing_broker_order_id = (
            closing_order_id
        )

        journal.close_snapshot = (
            _json_safe(
                closing_order
            )
        )

        journal.exit_debit = (
            exit_debit
        )

        journal.realized_pnl = (
            realized_pnl
        )

        journal.closed_at = (
            closed_at
        )

        journal.outcome = (
            _trade_outcome(
                realized_pnl
            )
        )

        journal.exit_reason = (
            "BROKER_CLOSE_ORDER"
        )

        session.commit()
        session.refresh(
            journal
        )

        return {
            "recorded": True,
            "changed": True,
            "status":
                journal.status,
            "closing_broker_order_id":
                journal.
                closing_broker_order_id,
            "entry_fill_credit":
                journal.
                entry_fill_credit,
            "exit_debit":
                journal.exit_debit,
            "realized_pnl":
                journal.realized_pnl,
            "outcome":
                journal.outcome,
        }


def reconcile_missing_trade_journals(
    active_positions,
    *,
    broker_client,
    session_factory=None,
):
    """
    Reconcile journal rows that are no longer present
    in the live-position set.

    Mere disappearance never closes a journal.
    A matching FILLED broker closing order is required.
    """

    if not database_configured():
        return {
            "checked": False,
            "reason":
                "DATABASE_NOT_CONFIGURED",
            "results": [],
        }

    active_order_ids = {
        str(
            position.get(
                "broker_order_id"
            )
            or ""
        ).strip()
        for position in (
            active_positions
            or []
        )
        if isinstance(
            position,
            dict,
        )
        and position.get(
            "broker_order_id"
        )
    }

    factory = (
        session_factory
        or get_session_factory()
    )

    with factory() as session:
        candidates = (
            session.execute(
                select(
                    TradeJournal
                )
                .where(
                    TradeJournal.status.in_(
                        (
                            "SUBMITTED",
                            "OPEN",
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

        candidates = [
            journal
            for journal
            in candidates
            if str(
                journal.broker_order_id
            ).strip()
            not in active_order_ids
        ]

        if not candidates:
            return {
                "checked": True,
                "candidates": 0,
                "results": [],
            }

        earliest = min(
            (
                journal.submitted_at
                for journal
                in candidates
                if journal.
                submitted_at
                is not None
            ),
            default=None,
        )

        start_date = (
            earliest.date()
            if earliest is not None
            else (
                datetime.now(
                    timezone.utc
                ).date()
                - timedelta(
                    days=14
                )
            )
        )

        journal_ids = [
            str(
                journal.
                broker_order_id
            ).strip()
            for journal
            in candidates
        ]

    account_number = (
        broker_client.
        get_first_account_number()
    )

    if not account_number:
        return {
            "checked": False,
            "reason":
                "BROKER_ACCOUNT_UNAVAILABLE",
            "results": [],
        }

    history = broker_client.get_orders(
        account_number=
            account_number,
        start_date=(
            start_date
            - timedelta(
                days=1
            )
        ).isoformat(),
        end_date=datetime.now(
            timezone.utc
        ).date().isoformat(),
        statuses=[
            "Filled",
        ],
    )

    by_id = {
        str(
            order.get("id")
            or ""
        ).strip(): order
        for order in (
            history
            or []
        )
        if isinstance(
            order,
            dict,
        )
        and order.get("id")
    }

    results = []
    used_close_ids = set()

    for opening_order_id in (
        journal_ids
    ):
        with factory() as session:
            journal = session.execute(
                select(
                    TradeJournal
                ).where(
                    TradeJournal.
                    broker_order_id
                    == opening_order_id
                )
            ).scalar_one_or_none()

            if journal is None:
                continue

            matching = [
                order
                for order in (
                    history
                    or []
                )
                if isinstance(
                    order,
                    dict,
                )
                and str(
                    order.get("id")
                    or ""
                ).strip()
                not in used_close_ids
                and _closing_order_matches(
                    journal,
                    order,
                )
            ]

        if not matching:
            results.append({
                "broker_order_id":
                    opening_order_id,
                "closed": False,
                "reason":
                    "NO_CONFIRMED_CLOSE_ORDER",
            })
            continue

        matching.sort(
            key=lambda order: (
                _order_fill_timestamp(
                    order
                )
                or datetime.max.replace(
                    tzinfo=timezone.utc
                )
            )
        )

        closing_order = (
            matching[0]
        )

        closing_order_id = str(
            closing_order.get("id")
            or ""
        ).strip()

        detailed_close = (
            broker_client.get_order(
                closing_order_id,
                account_number=
                    account_number,
            )
            or closing_order
        )

        opening_order = (
            by_id.get(
                opening_order_id
            )
            or broker_client.get_order(
                opening_order_id,
                account_number=
                    account_number,
            )
        )

        result = (
            finalize_closed_trade(
                broker_order_id=
                    opening_order_id,
                closing_order=
                    detailed_close,
                opening_order=
                    opening_order,
                session_factory=
                    factory,
            )
        )

        if (
            result.get(
                "recorded"
            )
            and result.get(
                "status"
            )
            == "CLOSED"
        ):
            used_close_ids.add(
                closing_order_id
            )

        results.append(
            result
        )

    return {
        "checked": True,
        "candidates":
            len(journal_ids),
        "results":
            results,
    }
