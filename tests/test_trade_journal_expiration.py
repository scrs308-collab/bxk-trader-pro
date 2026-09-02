from sqlalchemy import select

import bxk_app.services.trade_journal_service as service

from bxk_app.brokers.tastytrade import (
    TastytradeBroker,
)

from bxk_app.db_models.trade_journal import (
    TradeJournal,
)

from tests.test_trade_journal import (
    make_factory,
    sample_order,
)

from tests.test_trade_journal_close import (
    FakeResponse,
    _broker_open_order,
)


def _expiration(
    symbol,
    action,
    quantity=2,
):
    return {
        "executed-at":
            "2026-09-02T20:00:00Z",
        "transaction-date":
            "2026-09-02",
        "transaction-type":
            "Receive Deliver",
        "transaction-sub-type":
            "Expiration",
        "action": action,
        "symbol": symbol,
        "underlying-symbol": "SPX",
        "quantity": float(
            quantity
        ),
        "value": 0.0,
        "value-effect": "None",
        "net-value": 0.0,
        "net-value-effect": "None",
    }


def _cash_settlement(
    symbol,
    subtype,
    value,
    effect,
    quantity=2,
):
    return {
        "executed-at":
            "2026-09-02T21:00:00Z",
        "transaction-date":
            "2026-09-02",
        "transaction-type":
            "Receive Deliver",
        "transaction-sub-type":
            subtype,
        "symbol": symbol,
        "underlying-symbol": "SPX",
        "quantity": float(
            quantity
        ),
        "value": float(
            value
        ),
        "value-effect": effect,
        "net-value": (
            float(value) + 5
            if effect == "Debit"
            else float(value) - 5
        ),
        "net-value-effect": effect,
    }


def _real_symbols_order():
    order = sample_order()

    order["legs"] = [
        {
            "action": "SELL",
            "option_type": "PUT",
            "strike": 6500,
            "symbol":
                "SPXW  260902P06500000",
        },
        {
            "action": "BUY",
            "option_type": "PUT",
            "strike": 6475,
            "symbol":
                "SPXW  260902P06475000",
        },
        {
            "action": "SELL",
            "option_type": "CALL",
            "strike": 6650,
            "symbol":
                "SPXW  260902C06650000",
        },
        {
            "action": "BUY",
            "option_type": "CALL",
            "strike": 6675,
            "symbol":
                "SPXW  260902C06675000",
        },
    ]

    return order


def _create_expiring_journal(
    factory,
    monkeypatch,
    order_id="OPEN-EXP",
):
    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    return service.record_submitted_trade(
        broker_order_id=
            order_id,
        broker_status="FILLED",
        order=_real_symbols_order(),
        reconciliation={
            "filled_quantity": 2,
            "average_fill_price":
                2.75,
            "updated_at":
                "2026-09-01T15:00:00Z",
        },
        session_factory=factory,
    )


def _all_otm_transactions():
    return [
        _expiration(
            "SPXW  260902P06500000",
            "Buy to Close",
        ),
        _expiration(
            "SPXW  260902P06475000",
            "Sell to Close",
        ),
        _expiration(
            "SPXW  260902C06650000",
            "Buy to Close",
        ),
        _expiration(
            "SPXW  260902C06675000",
            "Sell to Close",
        ),
    ]


def _max_loss_put_settlement():
    return [
        _cash_settlement(
            "SPXW  260902P06500000",
            "Cash Settled Assignment",
            8000,
            "Debit",
        ),
        _cash_settlement(
            "SPXW  260902P06475000",
            "Cash Settled Exercise",
            3000,
            "Credit",
        ),
        _expiration(
            "SPXW  260902C06650000",
            "Buy to Close",
        ),
        _expiration(
            "SPXW  260902C06675000",
            "Sell to Close",
        ),
    ]


def test_expired_worthless_records_full_credit(
    monkeypatch,
):
    factory = make_factory()

    _create_expiring_journal(
        factory,
        monkeypatch,
    )

    result = service.finalize_expired_trade(
        broker_order_id="OPEN-EXP",
        transactions=
            _all_otm_transactions(),
        session_factory=factory,
    )

    assert result["status"] == "EXPIRED"
    assert result["exit_debit"] == 0.0
    assert result["realized_pnl"] == 550.0
    assert result["outcome"] == "WIN"

    assert (
        result["exit_reason"]
        == "EXPIRED_WORTHLESS"
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
        ).scalar_one()

        assert (
            journal.
            closing_broker_order_id
            is None
        )


def test_cash_settlement_uses_value_not_net_value(
    monkeypatch,
):
    factory = make_factory()

    _create_expiring_journal(
        factory,
        monkeypatch,
    )

    result = service.finalize_expired_trade(
        broker_order_id="OPEN-EXP",
        transactions=
            _max_loss_put_settlement(),
        session_factory=factory,
    )

    # $8,000 debit - $3,000 credit
    # = $5,000 settlement debit
    # = 25 points x 2 x $100.
    assert result["exit_debit"] == 25.0

    assert (
        result["realized_pnl"]
        == -4450.0
    )

    assert result["outcome"] == "LOSS"

    assert (
        result["exit_reason"]
        == "SPX_CASH_SETTLEMENT"
    )


def test_incomplete_expiration_does_not_finalize(
    monkeypatch,
):
    factory = make_factory()

    _create_expiring_journal(
        factory,
        monkeypatch,
    )

    transactions = (
        _all_otm_transactions()[:3]
    )

    result = service.finalize_expired_trade(
        broker_order_id="OPEN-EXP",
        transactions=transactions,
        session_factory=factory,
    )

    assert result["recorded"] is False

    assert (
        result["reason"]
        == "INCOMPLETE_SETTLEMENT_EVIDENCE"
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
        ).scalar_one()

        assert journal.status == "OPEN"


def test_transaction_history_paginates(
    monkeypatch,
):
    client = TastytradeBroker()

    calls = []

    payloads = [
        {
            "data": {
                "items": [
                    {
                        "id": "TX-1",
                    }
                ],
            },
            "pagination": {
                "total-pages": 2,
            },
        },
        {
            "data": {
                "items": [
                    {
                        "id": "TX-2",
                    }
                ],
            },
            "pagination": {
                "total-pages": 2,
            },
        },
    ]

    def fake_request(
        method,
        path,
        *,
        params=None,
        json_body=None,
    ):
        calls.append(
            (
                method,
                path,
                params,
            )
        )

        return FakeResponse(
            payloads[
                len(calls) - 1
            ]
        )

    monkeypatch.setattr(
        client,
        "_request",
        fake_request,
    )

    result = client.get_transactions(
        account_number="ACCOUNT",
        start_date="2026-09-01",
        end_date="2026-09-02",
        instrument_type=
            "Equity Option",
    )

    assert [
        item["id"]
        for item in result
    ] == [
        "TX-1",
        "TX-2",
    ]

    assert (
        calls[0][1]
        == "/accounts/ACCOUNT/transactions"
    )

    assert (
        calls[1][2][
            "page-offset"
        ]
        == 1
    )


def test_reconciler_falls_back_to_expiration(
    monkeypatch,
):
    factory = make_factory()

    _create_expiring_journal(
        factory,
        monkeypatch,
    )

    opening = _broker_open_order(
        order_id="OPEN-EXP"
    )

    class Broker:
        last_error = None

        def get_first_account_number(
            self,
        ):
            return "ACCOUNT"

        def get_orders(
            self,
            **kwargs,
        ):
            return [
                opening,
            ]

        def get_transactions(
            self,
            **kwargs,
        ):
            return (
                _all_otm_transactions()
            )

        def get_order(
            self,
            order_id,
            account_number=None,
        ):
            if order_id == "OPEN-EXP":
                return opening

            return None

    result = (
        service.
        reconcile_missing_trade_journals(
            [],
            broker_client=Broker(),
            session_factory=factory,
        )
    )

    assert (
        result["results"][0][
            "status"
        ]
        == "EXPIRED"
    )

    assert (
        result["results"][0][
            "realized_pnl"
        ]
        == 550.0
    )
