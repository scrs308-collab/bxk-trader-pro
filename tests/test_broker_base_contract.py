import pytest

from bxk_app.brokers.base import BrokerBase
from bxk_app.brokers.tastytrade import TastytradeBroker


class DummyBroker(BrokerBase):
    broker_name = "dummy"

    def authenticate(self):
        return True

    def get_status(self):
        return {}

    def get_accounts(self):
        return []

    def get_balances(self, account_number=None):
        return {}

    def get_positions(self, account_number=None):
        return []

    def get_quote(self, symbol: str):
        return {}


def test_broker_base_capability_defaults():
    broker = DummyBroker()

    assert broker.broker_name == "dummy"
    assert broker.supports("accounts") is False

    with pytest.raises(
        NotImplementedError,
        match="dummy does not support default account selection",
    ):
        broker.get_default_account_number()

    with pytest.raises(
        NotImplementedError,
        match="dummy does not support order lookup",
    ):
        broker.get_order("TEST123")

    with pytest.raises(
        NotImplementedError,
        match="dummy does not support order preview",
    ):
        broker.preview_order({})

    with pytest.raises(
        NotImplementedError,
        match="dummy does not support order submission",
    ):
        broker.submit_order({})


def test_tastytrade_default_account_delegates_to_legacy_selector(
    monkeypatch,
):
    broker = TastytradeBroker()

    monkeypatch.setattr(
        broker,
        "get_first_account_number",
        lambda: "TEST123",
    )

    assert (
        broker.get_default_account_number()
        == "TEST123"
    )


def test_tastytrade_declares_universal_capabilities():
    broker = TastytradeBroker()

    assert broker.broker_name == "tastytrade"
    assert broker.supports("accounts") is True
    assert broker.supports("balances") is True
    assert broker.supports("positions") is True
    assert broker.supports("quotes") is True
    assert broker.supports("order_preview") is True
    assert broker.supports("order_submission") is True
    assert broker.supports("cancel_order") is False


def test_tastytrade_preview_order_delegates_to_dry_run(monkeypatch):
    broker = TastytradeBroker()

    captured = {}

    def fake_dry_run_order(order, account_number=None):
        captured["order"] = order
        captured["account_number"] = account_number
        return {"ok": True}

    monkeypatch.setattr(
        broker,
        "dry_run_order",
        fake_dry_run_order,
    )

    order = {"strategy": "iron_condor"}

    result = broker.preview_order(
        order,
        account_number="TEST123",
    )

    assert result == {"ok": True}
    assert captured["order"] == order
    assert captured["account_number"] == "TEST123"


def test_tastytrade_submit_order_delegates_to_live_submission(
    monkeypatch,
):
    broker = TastytradeBroker()

    captured = {}

    def fake_submit_live_order(order, account_number=None):
        captured["order"] = order
        captured["account_number"] = account_number
        return {"submitted": True}

    monkeypatch.setattr(
        broker,
        "submit_live_order",
        fake_submit_live_order,
    )

    order = {"strategy": "vertical"}

    result = broker.submit_order(
        order,
        account_number="TEST456",
    )

    assert result == {"submitted": True}
    assert captured["order"] == order
    assert captured["account_number"] == "TEST456"
