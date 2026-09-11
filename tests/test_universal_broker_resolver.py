import pytest

from bxk_app.services import broker_connection_service as service


def test_normalize_broker_name():
    assert service.normalize_broker_name("tastytrade") == "tastytrade"
    assert service.normalize_broker_name(" TASTYTRADE ") == "tastytrade"
    assert service.normalize_broker_name(None) == ""


def test_supported_brokers_contains_tastytrade():
    assert "tastytrade" in service.SUPPORTED_BROKERS


def test_resolve_broker_dispatches_tastytrade(monkeypatch):
    expected = object()
    captured = {}

    def fake_resolve_tastytrade_broker(
        session,
        *,
        user_context,
    ):
        captured["session"] = session
        captured["user_context"] = user_context
        return expected

    monkeypatch.setattr(
        service,
        "resolve_tastytrade_broker",
        fake_resolve_tastytrade_broker,
    )

    fake_session = object()
    fake_context = {
        "id": "user-1",
        "role": "BETA",
    }

    result = service.resolve_broker(
        fake_session,
        user_context=fake_context,
        broker_name="TASTYTRADE",
    )

    assert result is expected
    assert captured["session"] is fake_session
    assert captured["user_context"] == fake_context


def test_resolve_broker_fails_closed_for_unknown_broker():
    with pytest.raises(
        service.BrokerConnectionRequired,
        match="not currently supported",
    ):
        service.resolve_broker(
            object(),
            user_context={
                "id": "user-1",
                "role": "BETA",
            },
            broker_name="schwab",
        )
