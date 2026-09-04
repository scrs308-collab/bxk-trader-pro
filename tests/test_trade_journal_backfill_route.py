from fastapi import FastAPI
from fastapi.testclient import TestClient

import bxk_app.routes.trade_journal as route_module

from bxk_app.services.broker_connection_service import (
    BrokerConnectionInvalid,
    BrokerConnectionRequired,
)


def make_client(
    monkeypatch,
    *,
    role,
    resolver,
):
    app = FastAPI()

    app.include_router(
        route_module.router
    )

    app.dependency_overrides[
        route_module.get_authenticated_user
    ] = lambda: {
        "user_id":
            "00000000-0000-0000-0000-000000000123",
        "role": role,
    }

    app.dependency_overrides[
        route_module.get_db
    ] = lambda: object()

    monkeypatch.setattr(
        route_module,
        "resolve_tastytrade_broker",
        resolver,
    )

    return TestClient(app)


def test_beta_backfill_uses_own_broker(
    monkeypatch,
):
    beta_broker = object()
    captured = {}

    def resolver(
        session,
        *,
        user_context,
    ):
        captured["resolver_user"] = (
            user_context
        )

        return beta_broker

    def fake_backfill(
        *,
        broker_client,
        user_context,
        days,
        dry_run,
    ):
        captured["broker"] = (
            broker_client
        )
        captured["backfill_user"] = (
            user_context
        )

        return {
            "ok": True,
            "dry_run": dry_run,
            "days": days,
        }

    monkeypatch.setattr(
        route_module,
        "backfill_trade_journal",
        fake_backfill,
    )

    client = make_client(
        monkeypatch,
        role="BETA",
        resolver=resolver,
    )

    response = client.post(
        "/api/trade-journal/backfill"
        "?days=14&dry_run=true"
    )

    assert response.status_code == 200
    assert captured["broker"] is beta_broker

    assert (
        captured["resolver_user"]["role"]
        == "BETA"
    )

    assert (
        captured["backfill_user"]["role"]
        == "BETA"
    )


def test_beta_backfill_without_broker_returns_409(
    monkeypatch,
):
    def resolver(
        session,
        *,
        user_context,
    ):
        raise BrokerConnectionRequired(
            "BETA broker required."
        )

    client = make_client(
        monkeypatch,
        role="BETA",
        resolver=resolver,
    )

    response = client.post(
        "/api/trade-journal/backfill"
    )

    assert response.status_code == 409


def test_invalid_backfill_broker_returns_400(
    monkeypatch,
):
    def resolver(
        session,
        *,
        user_context,
    ):
        raise BrokerConnectionInvalid(
            "Stored broker is invalid."
        )

    client = make_client(
        monkeypatch,
        role="BETA",
        resolver=resolver,
    )

    response = client.post(
        "/api/trade-journal/backfill"
    )

    assert response.status_code == 400


def test_viewer_backfill_blocked_before_broker_resolution(
    monkeypatch,
):
    def resolver(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "VIEWER must not resolve a broker."
        )

    client = make_client(
        monkeypatch,
        role="VIEWER",
        resolver=resolver,
    )

    response = client.post(
        "/api/trade-journal/backfill"
    )

    assert response.status_code == 403
