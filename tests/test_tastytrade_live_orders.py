import pytest

from bxk_app.brokers.tastytrade import (
    TastytradeBroker,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_get_order_fetches_exact_order(monkeypatch):
    broker = TastytradeBroker()
    request = {}

    def fake_request(
        method,
        path,
        *,
        params=None,
        json_body=None,
    ):
        request.update({
            "method": method,
            "path": path,
        })
        return FakeResponse({
            "data": {
                "order": {
                    "id": "ORDER-77",
                    "status": "Filled",
                },
            },
        })

    monkeypatch.setattr(
        broker,
        "_request",
        fake_request,
    )

    order = broker.get_order(
        "ORDER-77",
        account_number="TEST7178",
    )

    assert order["id"] == "ORDER-77"
    assert order["status"] == "Filled"
    assert request == {
        "method": "GET",
        "path": (
            "/accounts/TEST7178/orders/ORDER-77"
        ),
    }


def test_get_order_rejects_path_characters(monkeypatch):
    broker = TastytradeBroker()

    monkeypatch.setattr(
        broker,
        "_request",
        lambda *args, **kwargs: pytest.fail(
            "Unsafe order ID reached the broker request."
        ),
    )

    assert broker.get_order(
        "../orders/live",
        account_number="TEST7178",
    ) is None
    assert broker.last_error == "Order ID is invalid."


def test_get_live_orders_reads_all_pages(
    monkeypatch,
):
    broker = TastytradeBroker()
    requests = []

    pages = [
        {
            "data": {
                "items": [
                    {
                        "id": "ORDER-1",
                    }
                ]
            },
            "pagination": {
                "total-pages": 2,
            },
        },
        {
            "data": {
                "items": [
                    {
                        "id": "ORDER-2",
                    }
                ]
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
        requests.append({
            "method": method,
            "path": path,
            "params": dict(params or {}),
        })

        return FakeResponse(
            pages[
                params["page-offset"]
            ]
        )

    monkeypatch.setattr(
        broker,
        "_request",
        fake_request,
    )

    orders = broker.get_live_orders(
        account_number="TEST7178",
    )

    assert [
        order["id"]
        for order in orders
    ] == [
        "ORDER-1",
        "ORDER-2",
    ]

    assert [
        request["params"]["page-offset"]
        for request in requests
    ] == [0, 1]

    assert all(
        request["path"]
        == (
            "/accounts/TEST7178"
            "/orders/live"
        )
        for request in requests
    )


def test_get_live_orders_fails_closed_on_request_error(
    monkeypatch,
):
    broker = TastytradeBroker()

    def failed_request(*args, **kwargs):
        broker.last_error = (
            "Test live-orders request failure."
        )
        return None

    monkeypatch.setattr(
        broker,
        "_request",
        failed_request,
    )

    orders = broker.get_live_orders(
        account_number="TEST7178",
    )

    assert orders == []
    assert (
        broker.last_error
        == "Test live-orders request failure."
    )


def test_get_live_orders_rejects_unsafe_pagination(
    monkeypatch,
):
    broker = TastytradeBroker()

    monkeypatch.setattr(
        broker,
        "_request",
        lambda *args, **kwargs: FakeResponse({
            "data": {
                "items": [],
            },
            "pagination": {
                "total-pages": 101,
            },
        }),
    )

    orders = broker.get_live_orders(
        account_number="TEST7178",
    )

    assert orders == []
    assert (
        broker.last_error
        == (
            "Unsafe Tastytrade live-orders "
            "pagination range."
        )
    )
