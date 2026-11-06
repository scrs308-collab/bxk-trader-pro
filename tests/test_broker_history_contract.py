"""Contract tests for the read-only Tastytrade Performance order-history path.

Fixtures follow Tastytrade's documented dasherized order keys and pagination
response. No broker credentials or trade submission are used.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from bxk_app.brokers.tastytrade import TastytradeBroker
import bxk_app.routes.trade_journal as route


def sample_order(order_id="100", status="Filled", price="1.25"):
    return {
        "id": order_id,
        "status": status,
        "account-number": "MOCK-ACCOUNT",
        "average-fill-price": price,
        "price-effect": "Credit",
        "terminal-at": "2026-11-04T15:30:00Z",
        "legs": [
            {"symbol": "SPXW  261106P06000000", "action": "Sell to Open", "quantity": "1",
             "fills": [{"filled-at": "2026-11-04T15:30:03Z"}]},
            {"symbol": "SPXW  261106P05975000", "action": "Buy to Open", "quantity": "1",
             "fills": [{"filled-at": "2026-11-04T15:30:04Z"}]},
        ],
    }


def fake_broker(orders, last_error=None):
    return SimpleNamespace(
        get_first_account_number=lambda: "MOCK-ACCOUNT",
        get_orders=lambda **kwargs: orders,
        last_error=last_error,
    )


def test_history_returns_only_filled_and_deduplicated(monkeypatch):
    orders = [
        sample_order("100"), sample_order("100"),
        sample_order("101", status="Live"),
        sample_order("102", status="Cancelled"),
        sample_order("103", price="0"),
    ]
    monkeypatch.setattr(route, "resolve_broker", lambda session, user_context: fake_broker(orders))
    result = route.broker_trade_history(days=30, user_context={"role": "OWNER"}, session=None)
    assert result["available"] is True
    assert result["count"] == 2
    assert [row["id"] for row in result["orders"]] == ["100", "103"]
    assert result["orders"][0]["filled_at"] == "2026-11-04T15:30:04+00:00"
    assert result["orders"][0]["legs"][0]["action"] == "Sell to Open"
    assert result["orders"][1]["price"] == "0"


@pytest.mark.parametrize("bad_orders", [
    {"data": {"items": []}}, [None], [{"status": "Filled", "legs": []}],
    [{"id": "12", "status": "Filled", "legs": {}}],
    [{"id": "12", "status": "Filled", "legs": [None]}],
])
def test_history_rejects_malformed_broker_data(monkeypatch, bad_orders):
    monkeypatch.setattr(route, "resolve_broker", lambda session, user_context: fake_broker(bad_orders))
    with pytest.raises(HTTPException) as exc:
        route.broker_trade_history(user_context={"role": "OWNER"}, session=None)
    assert exc.value.status_code == 502


def test_history_reports_broker_failure_not_empty_success(monkeypatch):
    monkeypatch.setattr(route, "resolve_broker", lambda session, user_context: fake_broker([], last_error="401"))
    with pytest.raises(HTTPException) as exc:
        route.broker_trade_history(user_context={"role": "OWNER"}, session=None)
    assert exc.value.status_code == 502


def test_adapter_parses_pages_and_uses_documented_request_filters(monkeypatch):
    broker = TastytradeBroker()
    monkeypatch.setattr(broker, "get_first_account_number", lambda: "MOCK-ACCOUNT")
    calls = []

    def request(method, path, *, params=None, **kwargs):
        calls.append((method, path, params))
        page = params["page-offset"]
        order = sample_order(str(100 + page))
        return SimpleNamespace(json=lambda: {
            "data": {"items": [order]},
            "pagination": {"total-pages": 2, "page-offset": page},
        })

    monkeypatch.setattr(broker, "_request", request)
    rows = broker.get_orders(
        account_number="MOCK-ACCOUNT",
        start_date="2026-11-01",
        end_date="2026-11-06",
        statuses=["Filled"],
    )
    assert len(rows) == 2
    assert [row["id"] for row in rows] == ["100", "101"]
    assert [call[2]["page-offset"] for call in calls] == [0, 1]
    assert all(call[0] == "GET" for call in calls)
    assert all(call[1] == "/accounts/MOCK-ACCOUNT/orders" for call in calls)
    assert all(call[2]["status[]"] == ["Filled"] for call in calls)
    assert all(call[2]["start-date"] == "2026-11-01" for call in calls)
    assert all(call[2]["end-date"] == "2026-11-06" for call in calls)


def test_adapter_handles_broker_error_without_partial_success(monkeypatch):
    broker = TastytradeBroker()
    def request(method, path, *, params=None, **kwargs):
        if params["page-offset"] == 1:
            broker.last_error = "HTTP 502"
            return None
        return SimpleNamespace(json=lambda: {
            "data": {"items": [sample_order()]},
            "pagination": {"total-pages": 2},
        })
    monkeypatch.setattr(broker, "_request", request)
    assert broker.get_orders(
        account_number="MOCK-ACCOUNT", start_date="2026-11-01",
        statuses=["Filled"],
    ) == []
    assert broker.last_error == "HTTP 502"
