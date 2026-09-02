from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

import bxk_app.services.trade_journal_backfill_service as backfill
import bxk_app.services.trade_journal_service as journal_service

from bxk_app.db_models.trade_journal import (
    TradeJournal,
)

from tests.test_trade_journal import (
    make_factory,
)


def _order(
    order_id,
    *,
    actions,
    quantity=2,
    price=2.50,
    price_effect="Credit",
    expiration="260902",
):
    symbols = [
        f"SPXW  {expiration}P06475000",
        f"SPXW  {expiration}P06500000",
        f"SPXW  {expiration}C06650000",
        f"SPXW  {expiration}C06675000",
    ]

    if price_effect == "Credit":
        fill_prices = [
            1.00,
            2.00,
            2.00,
            0.50,
        ]
    else:
        fill_prices = [
            0.50,
            1.00,
            1.00,
            1.00,
        ]

    return {
        "id": order_id,
        "status": "Filled",
        "price": price,
        "price-effect":
            price_effect,
        "size": quantity,
        "received-at":
            "2026-09-01T15:00:00+00:00",
        "terminal-at":
            "2026-09-01T15:00:01+00:00",
        "legs": [
            {
                "symbol": symbol,
                "action": action,
                "quantity":
                    quantity,
                "instrument-type":
                    "Equity Option",
                "fills": [
                    {
                        "fill-price":
                            str(fill_price),
                        "quantity":
                            quantity,
                        "filled-at":
                            "2026-09-01T15:00:01+00:00",
                    }
                ],
            }
            for (
                symbol,
                action,
                fill_price,
            )
            in zip(
                symbols,
                actions,
                fill_prices,
            )
        ],
    }


def _opening(
    order_id="OPEN-1",
):
    return _order(
        order_id,
        actions=[
            "Buy to Open",
            "Sell to Open",
            "Sell to Open",
            "Buy to Open",
        ],
        price=2.50,
        price_effect="Credit",
    )


def _closing(
    order_id="CLOSE-1",
):
    order = _order(
        order_id,
        actions=[
            "Sell to Close",
            "Buy to Close",
            "Buy to Close",
            "Sell to Close",
        ],
        price=0.50,
        price_effect="Debit",
    )

    order["received-at"] = (
        "2026-09-02T15:00:00+00:00"
    )

    order["terminal-at"] = (
        "2026-09-02T15:00:01+00:00"
    )

    for leg in order["legs"]:
        for fill in (
            leg.get("fills")
            or []
        ):
            fill["filled-at"] = (
                "2026-09-02T15:00:01+00:00"
            )

    return order


class Broker:
    last_error = None

    def __init__(
        self,
        orders,
        transactions=None,
    ):
        self.orders = orders
        self.transactions = (
            transactions
            or []
        )

    def get_first_account_number(
        self,
    ):
        return "ACCOUNT"

    def get_orders(
        self,
        **kwargs,
    ):
        return self.orders

    def get_transactions(
        self,
        **kwargs,
    ):
        return self.transactions


def test_backfill_dry_run_finds_normal_close(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        journal_service,
        "database_configured",
        lambda: True,
    )

    result = (
        backfill.
        backfill_trade_journal(
            broker_client=Broker([
                _opening(),
                _closing(),
            ]),
            dry_run=True,
            now=datetime(
                2026,
                9,
                2,
                22,
                0,
                tzinfo=timezone.utc,
            ),
            session_factory=factory,
        )
    )

    assert result["ok"] is True
    assert result["opening_condors"] == 1

    trade = result["trades"][0]

    assert (
        trade["resolution"]
        == "BROKER_CLOSE_ORDER"
    )

    assert trade["exit_debit"] == 0.5
    assert trade["realized_pnl"] == 400.0

    with factory() as session:
        assert (
            session.execute(
                select(
                    TradeJournal
                )
            )
            .scalars()
            .all()
            == []
        )


def test_backfill_write_imports_closed_trade(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        journal_service,
        "database_configured",
        lambda: True,
    )

    result = (
        backfill.
        backfill_trade_journal(
            broker_client=Broker([
                _opening(),
                _closing(),
            ]),
            dry_run=False,
            now=datetime(
                2026,
                9,
                2,
                22,
                0,
                tzinfo=timezone.utc,
            ),
            session_factory=factory,
        )
    )

    assert result["ok"] is True
    assert result["imported"] == 1
    assert result["finalized"] == 1

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
        ).scalar_one()

        assert journal.status == "CLOSED"

        assert (
            journal.realized_pnl
            == 400.0
        )

        assert journal.dte == 1
        assert journal.quantity == 2


def test_backfill_is_idempotent(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        journal_service,
        "database_configured",
        lambda: True,
    )

    broker = Broker([
        _opening(),
        _closing(),
    ])

    first = (
        backfill.
        backfill_trade_journal(
            broker_client=broker,
            dry_run=False,
            now=datetime(
                2026,
                9,
                2,
                22,
                0,
                tzinfo=timezone.utc,
            ),
            session_factory=factory,
        )
    )

    second = (
        backfill.
        backfill_trade_journal(
            broker_client=broker,
            dry_run=False,
            now=datetime(
                2026,
                9,
                2,
                22,
                0,
                tzinfo=timezone.utc,
            ),
            session_factory=factory,
        )
    )

    assert first["imported"] == 1
    assert second["imported"] == 0

    assert (
        second["counts"][
            "ALREADY_JOURNALED"
        ]
        == 1
    )

    with factory() as session:
        rows = (
            session.execute(
                select(
                    TradeJournal
                )
            )
            .scalars()
            .all()
        )

        assert len(rows) == 1


def test_backfill_imports_current_open_trade(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        journal_service,
        "database_configured",
        lambda: True,
    )

    result = (
        backfill.
        backfill_trade_journal(
            broker_client=Broker([
                _opening(),
            ]),
            dry_run=False,
            now=datetime(
                2026,
                9,
                1,
                22,
                0,
                tzinfo=timezone.utc,
            ),
            session_factory=factory,
        )
    )

    assert result["imported"] == 1
    assert result["open_imported"] == 1

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
        ).scalar_one()

        assert journal.status == "OPEN"


def test_backfill_refuses_ambiguous_identical_condors(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        journal_service,
        "database_configured",
        lambda: True,
    )

    result = (
        backfill.
        backfill_trade_journal(
            broker_client=Broker([
                _opening(
                    "OPEN-1"
                ),
                _opening(
                    "OPEN-2"
                ),
            ]),
            dry_run=False,
            now=datetime(
                2026,
                9,
                1,
                22,
                0,
                tzinfo=timezone.utc,
            ),
            session_factory=factory,
        )
    )

    assert result["imported"] == 0

    assert (
        result["counts"][
            "AMBIGUOUS_IDENTICAL_CONDOR"
        ]
        == 2
    )

    with factory() as session:
        rows = (
            session.execute(
                select(
                    TradeJournal
                )
            )
            .scalars()
            .all()
        )

        assert rows == []

def test_backfill_route_registered_on_main_application():
    from bxk_app.main import app

    paths = set(
        app.openapi()
        .get("paths", {})
        .keys()
    )

    assert (
        "/api/trade-journal/backfill"
        in paths
    )

    methods = (
        app.openapi()["paths"][
            "/api/trade-journal/backfill"
        ]
    )

    assert "post" in methods

