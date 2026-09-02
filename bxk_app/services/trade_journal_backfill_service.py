from collections import defaultdict
from datetime import datetime, timedelta
import re
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import select

from bxk_app.db_models.trade_journal import TradeJournal
import bxk_app.services.trade_journal_service as journal_service


EASTERN = ZoneInfo(
    "America/New_York"
)

_OCC_PATTERN = re.compile(
    r"^SPXW\s+(\d{6})([CP])(\d{8})$"
)


def _normalize_action(value):
    return " ".join(
        str(value or "")
        .strip()
        .upper()
        .split()
    )


def _option_details(symbol):
    clean = str(
        symbol or ""
    ).strip()

    match = _OCC_PATTERN.match(
        clean
    )

    if not match:
        return None

    expiration = datetime.strptime(
        match.group(1),
        "%y%m%d",
    ).date()

    option_type = (
        "PUT"
        if match.group(2) == "P"
        else "CALL"
    )

    strike = (
        int(match.group(3))
        / 1000.0
    )

    return {
        "symbol": clean,
        "expiration": expiration,
        "option_type": option_type,
        "strike": strike,
    }


def _order_timestamp(order):
    value = (
        journal_service.
        _order_fill_timestamp(
            order
        )
    )

    if value is not None:
        return value

    return journal_service._datetime(
        order.get("received-at")
        or order.get("terminal-at")
    )


def _order_received_at(order):
    return journal_service._datetime(
        order.get("received-at")
    ) or _order_timestamp(order)


def _order_date(order):
    timestamp = _order_timestamp(
        order
    )

    if timestamp is None:
        return None

    if timestamp.tzinfo is None:
        return timestamp.date()

    return (
        timestamp
        .astimezone(EASTERN)
        .date()
    )


def _common_quantity(legs):
    values = []

    for leg in legs:
        quantity = (
            journal_service._number(
                leg.get("quantity")
            )
        )

        if (
            quantity is None
            or quantity <= 0
        ):
            return None

        values.append(
            float(quantity)
        )

    if not values:
        return None

    first = values[0]

    if any(
        abs(value - first)
        > 0.000001
        for value in values
    ):
        return None

    return int(first)


def _parse_four_leg_order(order):
    if not isinstance(
        order,
        dict,
    ):
        return None

    legs = (
        order.get("legs")
        or []
    )

    if len(legs) != 4:
        return None

    quantity = _common_quantity(
        legs
    )

    if quantity is None:
        return None

    parsed_legs = []

    for leg in legs:
        if not isinstance(
            leg,
            dict,
        ):
            return None

        details = _option_details(
            leg.get("symbol")
        )

        if details is None:
            return None

        parsed_legs.append({
            **details,
            "action":
                _normalize_action(
                    leg.get("action")
                ),
            "quantity":
                quantity,
        })

    expirations = {
        leg["expiration"]
        for leg in parsed_legs
    }

    if len(expirations) != 1:
        return None

    order_id = str(
        order.get("id")
        or ""
    ).strip()

    if not order_id:
        return None

    return {
        "id": order_id,
        "order": order,
        "legs": parsed_legs,
        "symbols": frozenset(
            leg["symbol"]
            for leg in parsed_legs
        ),
        "quantity": quantity,
        "expiration":
            next(iter(expirations)),
        "timestamp":
            _order_timestamp(
                order
            ),
        "received_at":
            _order_received_at(
                order
            ),
        "trade_date":
            _order_date(
                order
            ),
    }


def _opening_condor(parsed):
    if parsed is None:
        return None

    legs = parsed["legs"]

    actions = [
        leg["action"]
        for leg in legs
    ]

    if (
        actions.count(
            "SELL TO OPEN"
        ) != 2
        or actions.count(
            "BUY TO OPEN"
        ) != 2
    ):
        return None

    puts = [
        leg
        for leg in legs
        if leg["option_type"]
        == "PUT"
    ]

    calls = [
        leg
        for leg in legs
        if leg["option_type"]
        == "CALL"
    ]

    if (
        len(puts) != 2
        or len(calls) != 2
    ):
        return None

    def find_leg(
        collection,
        action,
    ):
        return next(
            (
                leg
                for leg in collection
                if leg["action"]
                == action
            ),
            None,
        )

    short_put = find_leg(
        puts,
        "SELL TO OPEN",
    )

    long_put = find_leg(
        puts,
        "BUY TO OPEN",
    )

    short_call = find_leg(
        calls,
        "SELL TO OPEN",
    )

    long_call = find_leg(
        calls,
        "BUY TO OPEN",
    )

    if not all(
        (
            short_put,
            long_put,
            short_call,
            long_call,
        )
    ):
        return None

    if not (
        long_put["strike"]
        < short_put["strike"]
        < short_call["strike"]
        < long_call["strike"]
    ):
        return None

    entry_credit = (
        journal_service.
        _opening_fill_credit(
            parsed["order"]
        )
    )

    if (
        entry_credit is None
        or entry_credit <= 0
    ):
        return None

    put_width = (
        short_put["strike"]
        - long_put["strike"]
    )

    call_width = (
        long_call["strike"]
        - short_call["strike"]
    )

    trade_date = parsed[
        "trade_date"
    ]

    dte = None

    if trade_date is not None:
        dte = (
            parsed["expiration"]
            - trade_date
        ).days

    return {
        **parsed,
        "entry_credit":
            float(entry_credit),
        "short_put":
            short_put["strike"],
        "long_put":
            long_put["strike"],
        "short_call":
            short_call["strike"],
        "long_call":
            long_call["strike"],
        "put_width":
            put_width,
        "call_width":
            call_width,
        "wing_width":
            max(
                put_width,
                call_width,
            ),
        "dte": dte,
        "open_actions": {
            leg["symbol"]:
                leg["action"]
            for leg in legs
        },
    }


def _closing_condor(parsed):
    if parsed is None:
        return None

    actions = [
        leg["action"]
        for leg in parsed["legs"]
    ]

    if (
        actions.count(
            "BUY TO CLOSE"
        ) != 2
        or actions.count(
            "SELL TO CLOSE"
        ) != 2
    ):
        return None

    return parsed


def _close_matches(
    opening,
    closing,
):
    if (
        opening["symbols"]
        != closing["symbols"]
    ):
        return False

    if (
        opening["quantity"]
        != closing["quantity"]
    ):
        return False

    if (
        opening["timestamp"]
        is not None
        and closing["timestamp"]
        is not None
        and closing["timestamp"]
        <= opening["timestamp"]
    ):
        return False

    close_actions = {
        leg["symbol"]:
            leg["action"]
        for leg in closing[
            "legs"
        ]
    }

    for (
        symbol,
        open_action,
    ) in opening[
        "open_actions"
    ].items():
        expected = (
            "BUY TO CLOSE"
            if open_action
            == "SELL TO OPEN"
            else "SELL TO CLOSE"
        )

        if (
            close_actions.get(
                symbol
            )
            != expected
        ):
            return False

    return True


def _journal_order_payload(
    opening,
):
    legs = []

    for leg in opening[
        "legs"
    ]:
        action = (
            "SELL"
            if leg["action"]
            == "SELL TO OPEN"
            else "BUY"
        )

        legs.append({
            "action": action,
            "option_type":
                leg["option_type"],
            "strike":
                leg["strike"],
            "symbol":
                leg["symbol"],
            "quantity":
                opening[
                    "quantity"
                ],
        })

    return {
        "strategy":
            "IRON_CONDOR",
        "underlying": "SPX",
        "expiration":
            opening[
                "expiration"
            ].isoformat(),
        "dte":
            opening["dte"],
        "quantity":
            opening[
                "quantity"
            ],
        "wing_width":
            opening[
                "wing_width"
            ],
        "submitted_credit":
            opening[
                "entry_credit"
            ],
        "credit":
            opening[
                "entry_credit"
            ],
        "legs": legs,
    }


def _settlement_preview(
    opening,
    transactions,
):
    synthetic_journal = (
        SimpleNamespace(
            expiration=
                opening[
                    "expiration"
                ],
            quantity=
                opening[
                    "quantity"
                ],
            entry_snapshot={
                "order":
                    _journal_order_payload(
                        opening
                    ),
            },
        )
    )

    evidence = (
        journal_service.
        _expiration_settlement_evidence(
            synthetic_journal,
            transactions,
        )
    )

    if not evidence.get(
        "complete"
    ):
        return {
            "resolved": False,
            "reason":
                evidence.get(
                    "reason"
                )
                or
                "INCOMPLETE_SETTLEMENT",
        }

    settlement_dollars = float(
        evidence[
            "settlement_dollars"
        ]
    )

    quantity = opening[
        "quantity"
    ]

    exit_debit = round(
        settlement_dollars
        / (
            100
            * quantity
        ),
        6,
    )

    realized_pnl = round(
        (
            opening[
                "entry_credit"
            ]
            * 100
            * quantity
        )
        - settlement_dollars,
        2,
    )

    return {
        "resolved": True,
        "reason": (
            "SPX_CASH_SETTLEMENT"
            if evidence[
                "cash_settled"
            ]
            else
            "EXPIRED_WORTHLESS"
        ),
        "exit_debit":
            exit_debit,
        "realized_pnl":
            realized_pnl,
    }


def _build_plan(
    *,
    orders,
    transactions,
    existing_ids,
    today,
):
    parsed_orders = []

    for order in (
        orders
        or []
    ):
        parsed = (
            _parse_four_leg_order(
                order
            )
        )

        if parsed is not None:
            parsed_orders.append(
                parsed
            )

    openings = []
    closings = []

    for parsed in parsed_orders:
        opening = (
            _opening_condor(
                parsed
            )
        )

        if opening is not None:
            openings.append(
                opening
            )
            continue

        closing = (
            _closing_condor(
                parsed
            )
        )

        if closing is not None:
            closings.append(
                closing
            )

    openings.sort(
        key=lambda item: (
            item["timestamp"]
            or datetime.min
        )
    )

    closings.sort(
        key=lambda item: (
            item["timestamp"]
            or datetime.min
        )
    )

    symbol_groups = defaultdict(
        list
    )

    for opening in openings:
        symbol_groups[
            opening[
                "symbols"
            ]
        ].append(
            opening
        )

    used_close_ids = set()
    plan = []

    for opening in openings:
        if opening["id"] in (
            existing_ids
            or set()
        ):
            plan.append({
                "opening": opening,
                "resolution":
                    "ALREADY_JOURNALED",
                "closing": None,
                "preview": None,
            })
            continue

        if (
            len(
                symbol_groups[
                    opening[
                        "symbols"
                    ]
                ]
            )
            > 1
        ):
            plan.append({
                "opening": opening,
                "resolution":
                    "AMBIGUOUS_IDENTICAL_CONDOR",
                "closing": None,
                "preview": None,
            })
            continue

        matches = [
            closing
            for closing in closings
            if (
                closing["id"]
                not in used_close_ids
                and _close_matches(
                    opening,
                    closing,
                )
            )
        ]

        if len(matches) > 1:
            plan.append({
                "opening": opening,
                "resolution":
                    "AMBIGUOUS_CLOSE_ORDERS",
                "closing": None,
                "preview": None,
            })
            continue

        if len(matches) == 1:
            closing = matches[0]

            used_close_ids.add(
                closing["id"]
            )

            exit_debit = (
                journal_service.
                _closing_exit_debit(
                    closing[
                        "order"
                    ]
                )
            )

            pnl = None

            if exit_debit is not None:
                pnl = round(
                    (
                        opening[
                            "entry_credit"
                        ]
                        - float(
                            exit_debit
                        )
                    )
                    * 100
                    * opening[
                        "quantity"
                    ],
                    2,
                )

            plan.append({
                "opening": opening,
                "resolution":
                    "BROKER_CLOSE_ORDER",
                "closing":
                    closing,
                "preview": {
                    "exit_debit":
                        exit_debit,
                    "realized_pnl":
                        pnl,
                },
            })
            continue

        if (
            opening[
                "expiration"
            ]
            > today
        ):
            plan.append({
                "opening": opening,
                "resolution":
                    "OPEN",
                "closing": None,
                "preview": None,
            })
            continue

        settlement = (
            _settlement_preview(
                opening,
                transactions,
            )
        )

        plan.append({
            "opening": opening,
            "resolution":
                settlement[
                    "reason"
                ],
            "closing": None,
            "preview":
                settlement,
        })

    return plan


def _existing_order_ids(
    *,
    session_factory=None,
):
    factory = (
        session_factory
        or journal_service.
        get_session_factory()
    )

    with factory() as session:
        return {
            str(value).strip()
            for value in (
                session.execute(
                    select(
                        TradeJournal.
                        broker_order_id
                    )
                )
                .scalars()
                .all()
            )
            if value
        }


def _normalize_imported_row(
    *,
    opening,
    session_factory=None,
):
    factory = (
        session_factory
        or journal_service.
        get_session_factory()
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            ).where(
                TradeJournal.
                broker_order_id
                == opening["id"]
            )
        ).scalar_one_or_none()

        if journal is None:
            return

        quantity = opening[
            "quantity"
        ]

        entry_credit = opening[
            "entry_credit"
        ]

        wing_width = opening[
            "wing_width"
        ]

        journal.strategy = (
            "IRON_CONDOR"
        )

        journal.underlying = "SPX"

        journal.expiration = (
            opening[
                "expiration"
            ]
        )

        journal.dte = (
            opening["dte"]
        )

        journal.quantity = (
            quantity
        )

        journal.wing_width = (
            wing_width
        )

        journal.short_put = (
            opening[
                "short_put"
            ]
        )

        journal.long_put = (
            opening[
                "long_put"
            ]
        )

        journal.short_call = (
            opening[
                "short_call"
            ]
        )

        journal.long_call = (
            opening[
                "long_call"
            ]
        )

        journal.submitted_credit = (
            entry_credit
        )

        journal.entry_fill_credit = (
            entry_credit
        )

        journal.max_profit = round(
            entry_credit
            * 100
            * quantity,
            2,
        )

        journal.max_risk = round(
            (
                wing_width
                - entry_credit
            )
            * 100
            * quantity,
            2,
        )

        if (
            opening[
                "received_at"
            ]
            is not None
        ):
            journal.submitted_at = (
                opening[
                    "received_at"
                ]
            )

        if (
            opening[
                "timestamp"
            ]
            is not None
        ):
            journal.opened_at = (
                opening[
                    "timestamp"
                ]
            )

        session.commit()


def _public_plan_row(item):
    opening = item[
        "opening"
    ]

    closing = item.get(
        "closing"
    )

    preview = (
        item.get("preview")
        or {}
    )

    return {
        "broker_order_id":
            opening["id"],
        "trade_date": (
            opening[
                "trade_date"
            ].isoformat()
            if opening[
                "trade_date"
            ]
            else None
        ),
        "expiration":
            opening[
                "expiration"
            ].isoformat(),
        "dte":
            opening["dte"],
        "quantity":
            opening[
                "quantity"
            ],
        "entry_credit":
            opening[
                "entry_credit"
            ],
        "long_put":
            opening[
                "long_put"
            ],
        "short_put":
            opening[
                "short_put"
            ],
        "short_call":
            opening[
                "short_call"
            ],
        "long_call":
            opening[
                "long_call"
            ],
        "resolution":
            item[
                "resolution"
            ],
        "closing_broker_order_id": (
            closing["id"]
            if closing
            else None
        ),
        "exit_debit":
            preview.get(
                "exit_debit"
            ),
        "realized_pnl":
            preview.get(
                "realized_pnl"
            ),
    }


def backfill_trade_journal(
    *,
    broker_client,
    user_context=None,
    days=30,
    dry_run=True,
    now=None,
    session_factory=None,
):
    """
    Import historical filled SPXW iron condors.

    Filled broker orders are authoritative for normal
    opens/closes. Tastytrade transaction history is used
    only for expiration and cash settlement.
    """

    if not (
        journal_service.
        database_configured()
    ):
        return {
            "ok": False,
            "reason":
                "DATABASE_NOT_CONFIGURED",
        }

    try:
        clean_days = int(
            days
        )
    except (
        TypeError,
        ValueError,
    ):
        clean_days = 30

    clean_days = max(
        1,
        min(
            clean_days,
            365,
        ),
    )

    current = (
        now
        or datetime.now(
            EASTERN
        )
    )

    today = (
        current.date()
    )

    start_date = (
        today
        - timedelta(
            days=clean_days
        )
    )

    account_number = (
        broker_client.
        get_first_account_number()
    )

    if not account_number:
        return {
            "ok": False,
            "reason":
                "BROKER_ACCOUNT_UNAVAILABLE",
        }

    orders = (
        broker_client.get_orders(
            account_number=
                account_number,
            start_date=
                start_date.isoformat(),
            end_date=
                today.isoformat(),
            statuses=["Filled"],
            underlying_symbol="SPX",
        )
        or []
    )

    if (
        not orders
        and getattr(
            broker_client,
            "last_error",
            None,
        )
    ):
        return {
            "ok": False,
            "reason":
                "BROKER_ORDER_HISTORY_FAILED",
            "error":
                str(
                    broker_client.
                    last_error
                ),
        }

    transactions = (
        broker_client.
        get_transactions(
            account_number=
                account_number,
            start_date=
                start_date.isoformat(),
            end_date=
                today.isoformat(),
            instrument_type=
                "Equity Option",
        )
        or []
    )

    existing_ids = (
        _existing_order_ids(
            session_factory=
                session_factory,
        )
    )

    plan = _build_plan(
        orders=orders,
        transactions=transactions,
        existing_ids=
            existing_ids,
        today=today,
    )

    public_plan = [
        _public_plan_row(
            item
        )
        for item in plan
    ]

    counts = defaultdict(
        int
    )

    for item in plan:
        counts[
            item[
                "resolution"
            ]
        ] += 1

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "days":
                clean_days,
            "start_date":
                start_date.isoformat(),
            "end_date":
                today.isoformat(),
            "filled_orders":
                len(orders),
            "opening_condors":
                len(plan),
            "counts":
                dict(counts),
            "trades":
                public_plan,
        }

    imported = 0
    finalized = 0
    open_imported = 0
    skipped = 0
    errors = []

    importable = {
        "BROKER_CLOSE_ORDER",
        "EXPIRED_WORTHLESS",
        "SPX_CASH_SETTLEMENT",
        "OPEN",
    }

    factory = (
        session_factory
        or journal_service.
        get_session_factory()
    )

    for item in plan:
        opening = item[
            "opening"
        ]

        resolution = item[
            "resolution"
        ]

        if resolution not in (
            importable
        ):
            skipped += 1
            continue

        result = (
            journal_service.
            record_submitted_trade(
                broker_order_id=
                    opening["id"],
                broker_status="FILLED",
                order=
                    _journal_order_payload(
                        opening
                    ),
                reconciliation={
                    "filled_quantity":
                        opening[
                            "quantity"
                        ],
                    "average_fill_price":
                        opening[
                            "entry_credit"
                        ],
                    "updated_at": (
                        opening[
                            "timestamp"
                        ].isoformat()
                        if opening[
                            "timestamp"
                        ]
                        else None
                    ),
                },
                user_context=
                    user_context,
                session_factory=
                    factory,
            )
        )

        if not result.get(
            "recorded"
        ):
            if result.get(
                "reason"
            ) in {
                "ALREADY_RECORDED",
                "JOURNAL_ALREADY_EXISTS",
            }:
                skipped += 1
                continue

            errors.append({
                "broker_order_id":
                    opening["id"],
                "stage":
                    "ENTRY",
                "result":
                    result,
            })
            continue

        imported += 1

        _normalize_imported_row(
            opening=opening,
            session_factory=factory,
        )

        if (
            resolution
            == "BROKER_CLOSE_ORDER"
        ):
            final_result = (
                journal_service.
                finalize_closed_trade(
                    broker_order_id=
                        opening["id"],
                    closing_order=
                        item[
                            "closing"
                        ][
                            "order"
                        ],
                    opening_order=
                        opening[
                            "order"
                        ],
                    session_factory=
                        factory,
                )
            )

            if (
                final_result.get(
                    "recorded"
                )
                and final_result.get(
                    "status"
                )
                == "CLOSED"
            ):
                finalized += 1
            else:
                errors.append({
                    "broker_order_id":
                        opening["id"],
                    "stage":
                        "CLOSE",
                    "result":
                        final_result,
                })

        elif resolution in {
            "EXPIRED_WORTHLESS",
            "SPX_CASH_SETTLEMENT",
        }:
            final_result = (
                journal_service.
                finalize_expired_trade(
                    broker_order_id=
                        opening["id"],
                    transactions=
                        transactions,
                    opening_order=
                        opening[
                            "order"
                        ],
                    session_factory=
                        factory,
                )
            )

            if (
                final_result.get(
                    "recorded"
                )
                and final_result.get(
                    "status"
                )
                == "EXPIRED"
            ):
                finalized += 1
            else:
                errors.append({
                    "broker_order_id":
                        opening["id"],
                    "stage":
                        "SETTLEMENT",
                    "result":
                        final_result,
                })

        elif resolution == "OPEN":
            open_imported += 1

    return {
        "ok":
            not errors,
        "dry_run": False,
        "days":
            clean_days,
        "start_date":
            start_date.isoformat(),
        "end_date":
            today.isoformat(),
        "filled_orders":
            len(orders),
        "opening_condors":
            len(plan),
        "imported":
            imported,
        "finalized":
            finalized,
        "open_imported":
            open_imported,
        "skipped":
            skipped,
        "errors":
            errors,
        "counts":
            dict(counts),
        "trades":
            public_plan,
    }
