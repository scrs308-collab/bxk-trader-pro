import json
import uuid
from datetime import (
    date,
    datetime,
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
