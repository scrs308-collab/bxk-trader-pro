from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    select,
)

import bxk_app.services.trade_journal_service as service
import bxk_app.services.position_service as position_service
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


class FakeResponse:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def json(self):
        return self.payload


def _broker_open_order(
    order_id="OPEN-1",
):
    return {
        "id": order_id,
        "status": "Filled",
        "price-effect": "Credit",
        "average-fill-price": "2.70",
        "terminal-at":
            "2026-09-02T14:01:00Z",
        "legs": [
            {
                "symbol": "PUT-SHORT",
                "action": "Sell to Open",
                "quantity": "2",
            },
            {
                "symbol": "PUT-LONG",
                "action": "Buy to Open",
                "quantity": "2",
            },
            {
                "symbol": "CALL-SHORT",
                "action": "Sell to Open",
                "quantity": "2",
            },
            {
                "symbol": "CALL-LONG",
                "action": "Buy to Open",
                "quantity": "2",
            },
        ],
    }


def _broker_close_order(
    order_id="CLOSE-1",
):
    return {
        "id": order_id,
        "status": "Filled",
        "price-effect": "Debit",
        "average-fill-price": "0.80",
        "terminal-at":
            "2026-09-02T18:30:00Z",
        "legs": [
            {
                "symbol": "PUT-SHORT",
                "action": "Buy to Close",
                "quantity": "2",
            },
            {
                "symbol": "PUT-LONG",
                "action": "Sell to Close",
                "quantity": "2",
            },
            {
                "symbol": "CALL-SHORT",
                "action": "Buy to Close",
                "quantity": "2",
            },
            {
                "symbol": "CALL-LONG",
                "action": "Sell to Close",
                "quantity": "2",
            },
        ],
    }


def _create_open_journal(
    factory,
    monkeypatch,
    order_id="OPEN-1",
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
        order=sample_order(),
        broker_order={
            "received-at":
                "2026-09-02T14:00:00Z",
        },
        reconciliation={
            "filled_quantity": 2,
            "average_fill_price":
                2.70,
            "updated_at":
                "2026-09-02T14:01:00Z",
        },
        session_factory=factory,
    )


def test_broker_order_history_paginates(
    monkeypatch,
):
    client = TastytradeBroker()

    calls = []

    payloads = [
        {
            "data": {
                "items": [
                    {
                        "id": "1",
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
                        "id": "2",
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

    orders = client.get_orders(
        account_number="ACCOUNT",
        start_date="2026-09-01",
        end_date="2026-09-02",
        statuses=["Filled"],
    )

    assert [
        item["id"]
        for item in orders
    ] == [
        "1",
        "2",
    ]

    assert (
        calls[0][1]
        == "/accounts/ACCOUNT/orders"
    )

    assert (
        calls[0][2][
            "status[]"
        ]
        == ["Filled"]
    )

    assert (
        calls[1][2][
            "page-offset"
        ]
        == 1
    )


def test_confirmed_close_records_realized_pnl(
    monkeypatch,
):
    factory = make_factory()

    _create_open_journal(
        factory,
        monkeypatch,
    )

    result = (
        service.finalize_closed_trade(
            broker_order_id=
                "OPEN-1",
            closing_order=
                _broker_close_order(),
            opening_order=
                _broker_open_order(),
            session_factory=factory,
        )
    )

    assert (
        result["status"]
        == "CLOSED"
    )

    assert (
        result[
            "closing_broker_order_id"
        ]
        == "CLOSE-1"
    )

    assert (
        result["entry_fill_credit"]
        == 2.70
    )

    assert (
        result["exit_debit"]
        == 0.80
    )

    assert (
        result["realized_pnl"]
        == 380.0
    )

    assert (
        result["outcome"]
        == "WIN"
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
        ).scalar_one()

        assert (
            journal.status
            == "CLOSED"
        )

        assert (
            journal.
            closing_broker_order_id
            == "CLOSE-1"
        )

        assert (
            journal.exit_reason
            == "BROKER_CLOSE_ORDER"
        )


def test_wrong_leg_actions_do_not_close(
    monkeypatch,
):
    factory = make_factory()

    _create_open_journal(
        factory,
        monkeypatch,
    )

    bad_close = (
        _broker_close_order()
    )

    bad_close["legs"][0][
        "action"
    ] = "Sell to Open"

    result = (
        service.finalize_closed_trade(
            broker_order_id=
                "OPEN-1",
            closing_order=
                bad_close,
            opening_order=
                _broker_open_order(),
            session_factory=factory,
        )
    )

    assert (
        result["recorded"]
        is False
    )

    assert (
        result["reason"]
        == "CLOSE_ORDER_MISMATCH"
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
        ).scalar_one()

        assert (
            journal.status
            == "OPEN"
        )


def test_active_position_is_never_reconciled_closed(
    monkeypatch,
):
    factory = make_factory()

    _create_open_journal(
        factory,
        monkeypatch,
    )

    class Broker:
        def get_first_account_number(
            self,
        ):
            raise AssertionError(
                "Broker history should not "
                "be queried for active trade."
            )

    result = (
        service.
        reconcile_missing_trade_journals(
            [
                {
                    "broker_order_id":
                        "OPEN-1",
                }
            ],
            broker_client=Broker(),
            session_factory=factory,
        )
    )

    assert (
        result["candidates"]
        == 0
    )


def test_disappeared_position_without_close_order_stays_open(
    monkeypatch,
):
    factory = make_factory()

    _create_open_journal(
        factory,
        monkeypatch,
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
                _broker_open_order()
            ]

        def get_order(
            self,
            order_id,
            account_number=None,
        ):
            if (
                order_id
                == "OPEN-1"
            ):
                return (
                    _broker_open_order()
                )

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
            "reason"
        ]
        == "NO_CONFIRMED_CLOSE_ORDER"
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
        ).scalar_one()

        assert (
            journal.status
            == "OPEN"
        )


def test_disappeared_position_with_confirmed_close_is_closed(
    monkeypatch,
):
    factory = make_factory()

    _create_open_journal(
        factory,
        monkeypatch,
    )

    opening = (
        _broker_open_order()
    )

    closing = (
        _broker_close_order()
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
                closing,
                opening,
            ]

        def get_order(
            self,
            order_id,
            account_number=None,
        ):
            if order_id == "OPEN-1":
                return opening

            if order_id == "CLOSE-1":
                return closing

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
        == "CLOSED"
    )

    assert (
        result["results"][0][
            "realized_pnl"
        ]
        == 380.0
    )


def test_empty_order_history_is_valid(
    monkeypatch,
):
    client = TastytradeBroker()

    def fake_request(
        method,
        path,
        *,
        params=None,
        json_body=None,
    ):
        return FakeResponse({
            "data": {
                "items": [],
            },
            "pagination": {
                "total-pages": 0,
            },
        })

    monkeypatch.setattr(
        client,
        "_request",
        fake_request,
    )

    result = client.get_orders(
        account_number="ACCOUNT",
        statuses=["Filled"],
    )

    assert result == []
    assert client.last_error is None


def test_closure_reconciliation_is_throttled(
    monkeypatch,
):
    calls = []

    monkeypatch.setenv(
        "BXK_TRADE_JOURNAL_RECONCILE_SECONDS",
        "60",
    )

    monkeypatch.setattr(
        position_service,
        "_JOURNAL_RECONCILE_NEXT_AT",
        0.0,
    )

    def fake_reconcile(
        positions,
        *,
        broker_client,
    ):
        calls.append(
            list(positions)
        )

        return {
            "checked": True,
            "results": [],
        }

    monkeypatch.setattr(
        position_service,
        "reconcile_missing_trade_journals",
        fake_reconcile,
    )

    broker = object()

    first = (
        position_service.
        _reconcile_trade_journal_closures(
            [],
            broker_client=broker,
            now_monotonic=100.0,
        )
    )

    second = (
        position_service.
        _reconcile_trade_journal_closures(
            [],
            broker_client=broker,
            now_monotonic=120.0,
        )
    )

    third = (
        position_service.
        _reconcile_trade_journal_closures(
            [],
            broker_client=broker,
            now_monotonic=160.0,
        )
    )

    assert first["checked"] is True

    assert second == {
        "checked": False,
        "reason": "THROTTLED",
        "results": [],
    }

    assert third["checked"] is True
    assert len(calls) == 2


def test_closure_reconciliation_failure_is_isolated(
    monkeypatch,
):
    monkeypatch.setattr(
        position_service,
        "_JOURNAL_RECONCILE_NEXT_AT",
        0.0,
    )

    def fail(
        positions,
        *,
        broker_client,
    ):
        raise RuntimeError(
            "broker history unavailable"
        )

    monkeypatch.setattr(
        position_service,
        "reconcile_missing_trade_journals",
        fail,
    )

    result = (
        position_service.
        _reconcile_trade_journal_closures(
            [],
            broker_client=object(),
            now_monotonic=100.0,
        )
    )

    assert result["checked"] is False
    assert (
        result["reason"]
        == "JOURNAL_RECONCILIATION_FAILED"
    )

    assert (
        result["error"]
        == "RuntimeError"
    )


def test_empty_live_positions_trigger_close_check(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        position_service.tastytrade_api,
        "authenticate",
        lambda: True,
    )

    monkeypatch.setattr(
        position_service.tastytrade_api,
        "get_position_summary",
        lambda: [],
    )

    monkeypatch.setattr(
        position_service,
        "_reconcile_trade_journal_closures",
        lambda positions: (
            calls.append(
                list(positions)
            )
            or {
                "checked": True,
            }
        ),
    )

    result = (
        position_service.
        get_position_monitor()
    )

    assert result["status"] == "EMPTY"
    assert calls == [[]]


def test_live_summaries_feed_close_reconciler(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        position_service.tastytrade_api,
        "authenticate",
        lambda: True,
    )

    monkeypatch.setattr(
        position_service.tastytrade_api,
        "get_position_summary",
        lambda: [
            {
                "symbol": "RAW",
            }
        ],
    )

    monkeypatch.setattr(
        position_service.market_data,
        "get_snapshot",
        lambda: {
            "spx": 6500,
        },
    )

    monkeypatch.setattr(
        position_service,
        "build_position_summaries",
        lambda **kwargs: [
            {
                "pnl": 0,
                "legs": [],
            }
        ],
    )

    linked = [{
        "pnl": 0,
        "legs": [],
        "broker_linked": True,
        "broker_order_id": "OPEN-1",
    }]

    monkeypatch.setattr(
        position_service,
        "link_positions_to_submissions",
        lambda summaries, submissions:
            linked,
    )

    monkeypatch.setattr(
        position_service,
        "read_recent_submitted_orders",
        lambda: [],
    )

    monkeypatch.setattr(
        position_service,
        "observe_linked_positions",
        lambda summaries: [],
    )

    monkeypatch.setattr(
        position_service,
        "_reconcile_trade_journal_closures",
        lambda summaries: (
            calls.append(
                list(summaries)
            )
            or {
                "checked": True,
            }
        ),
    )

    result = (
        position_service.
        get_position_monitor()
    )

    assert result["status"] == "OK"

    assert (
        calls[0][0][
            "broker_order_id"
        ]
        == "OPEN-1"
    )
