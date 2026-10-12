"""HTTP identity, validation, and observation-only contract checks."""

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from bxk_app import config
import bxk_app.routes.stop_audit as route
from bxk_app.services.broker_connection_service import BrokerConnectionInvalid, BrokerConnectionRequired


USER_ID = str(uuid.UUID(int=123))
JOURNAL_ID = str(uuid.UUID(int=456))
CONTEXT = {"user_id": USER_ID, "role": "BETA"}


def payload(**changes):
    body = {"journal_id": JOURNAL_ID, "confirm_stop_out": True, "entry_costs": 8,
            "actual_exit_costs": 4, "hypothetical_exit_costs": 6}
    body.update(changes)
    return body


def make_client(monkeypatch, context=CONTEXT):
    app = FastAPI()
    app.include_router(route.router)
    monkeypatch.setattr(config, "BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED", False)
    @app.middleware("http")
    async def identity(request, call_next):
        if context is not None:
            request.state.bxk_user = dict(context)
        return await call_next(request)
    app.dependency_overrides[route.get_db] = lambda: object()
    return TestClient(app)


def test_get_passes_only_authenticated_context_to_the_audit_service(monkeypatch):
    captured = {}
    expected = {"enabled": True, "audits": [], "candidates": []}
    def list_audits(**kwargs):
        captured.update(kwargs)
        return expected
    monkeypatch.setattr(route, "get_stop_audits", list_audits)
    response = make_client(monkeypatch).get("/api/stop-audit?user_id=someone-else")
    assert response.status_code == 200
    assert response.json() == expected
    assert captured == {"user_context": CONTEXT}


def test_enrollment_resolves_authenticated_users_tastytrade_client(monkeypatch):
    captured = {}
    broker = object()
    def resolve(session, **kwargs):
        captured["resolution"] = kwargs
        return broker
    def enroll(**kwargs):
        captured["enrollment"] = kwargs
        return {"id": "new-audit", "actual_net_pnl": -612}
    monkeypatch.setattr(route, "resolve_broker", resolve)
    monkeypatch.setattr(route, "enroll_stop_audit", enroll)
    response = make_client(monkeypatch).post("/api/stop-audit", json=payload())
    assert response.status_code == 200
    assert response.json()["actual_net_pnl"] == -612
    assert captured["resolution"] == {"user_context": CONTEXT, "broker_name": "tastytrade"}
    assert captured["enrollment"] == {**payload(), "user_context": CONTEXT, "broker_client": broker}


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("context", [None, {"user_id": USER_ID, "role": "VIEWER"}])
def test_unauthenticated_and_viewer_requests_fail_before_broker_reads(monkeypatch, method, context):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unauthorized requests cannot access private audits or a broker")
    monkeypatch.setattr(route, "resolve_broker", forbidden)
    monkeypatch.setattr(route, "enroll_stop_audit", forbidden)
    monkeypatch.setattr(route, "get_stop_audits", forbidden)
    client = make_client(monkeypatch, context=context)
    kwargs = {"json": payload()} if method == "post" else {}
    response = getattr(client, method)("/api/stop-audit", **kwargs)
    assert response.status_code == 403


@pytest.mark.parametrize("field", ["journal_id", "confirm_stop_out", "entry_costs",
                                    "actual_exit_costs", "hypothetical_exit_costs"])
def test_all_enrollment_fields_are_explicitly_required(monkeypatch, field):
    body = payload()
    del body[field]
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid enrollment cannot resolve a broker")
    monkeypatch.setattr(route, "resolve_broker", forbidden)
    response = make_client(monkeypatch).post("/api/stop-audit", json=body)
    assert response.status_code == 422


@pytest.mark.parametrize("changes", [
    {"confirm_stop_out": "yes"}, {"confirm_stop_out": 1}, {"journal_id": "not-a-uuid"},
    {"entry_costs": -1}, {"actual_exit_costs": None}, {"hypothetical_exit_costs": "NaN"},
    {"entry_costs": "Infinity"}, {"entry_costs": 1_000_001},
])
def test_malformed_confirmation_or_costs_are_rejected_before_broker_resolution(monkeypatch, changes):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid request must not access the broker")
    monkeypatch.setattr(route, "resolve_broker", forbidden)
    response = make_client(monkeypatch).post("/api/stop-audit", json=payload(**changes))
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["entry_costs", "actual_exit_costs", "hypothetical_exit_costs"])
@pytest.mark.parametrize("value", [True, False])
def test_boolean_costs_cannot_bypass_numeric_service_validation(monkeypatch, field, value):
    reads = []
    monkeypatch.setattr(route, "resolve_broker", lambda *args, **kwargs: reads.append(kwargs))
    monkeypatch.setattr(route, "enroll_stop_audit", lambda **kwargs: {"id": "should-not-enroll"})
    response = make_client(monkeypatch).post("/api/stop-audit", json=payload(**{field: value}))
    assert response.status_code == 422
    assert reads == []


@pytest.mark.parametrize("error", [BrokerConnectionRequired("Connect your broker"),
                                    BrokerConnectionInvalid("Invalid broker connection")])
def test_broker_connection_failure_has_no_shared_account_fallback(monkeypatch, error):
    def resolve(*args, **kwargs):
        raise error
    def forbidden(*args, **kwargs):
        raise AssertionError("Enrollment requires the authenticated user's broker")
    monkeypatch.setattr(route, "resolve_broker", resolve)
    monkeypatch.setattr(route, "enroll_stop_audit", forbidden)
    response = make_client(monkeypatch).post("/api/stop-audit", json=payload())
    assert response.status_code == 409


@pytest.mark.parametrize("error,expected", [(PermissionError("Trade unavailable."), 403),
                                             (ValueError("Quotes are not enough to verify a fill."), 409)])
def test_service_failures_are_safe_client_errors(monkeypatch, error, expected):
    monkeypatch.setattr(route, "resolve_broker", lambda *args, **kwargs: object())
    def fail(**kwargs):
        raise error
    monkeypatch.setattr(route, "enroll_stop_audit", fail)
    response = make_client(monkeypatch).post("/api/stop-audit", json=payload())
    assert response.status_code == expected
    assert response.json()["detail"] == str(error)


def test_client_cannot_override_authenticated_owner_or_broker(monkeypatch):
    captured = {}
    broker = object()
    monkeypatch.setattr(route, "resolve_broker", lambda *args, **kwargs: broker)
    def enroll(**kwargs):
        captured.update(kwargs)
        return {"id": "audit"}
    monkeypatch.setattr(route, "enroll_stop_audit", enroll)
    body = payload(user_context={"user_id": "other-user", "role": "OWNER"},
                   user_id="other-user", broker_client="other-broker")
    response = make_client(monkeypatch).post("/api/stop-audit", json=body)
    assert response.status_code in {200, 422}
    if response.status_code == 200:
        assert captured["user_context"] == CONTEXT
        assert captured["broker_client"] is broker
        assert "user_id" not in captured


def test_route_surface_has_no_order_execution_or_manual_sampler_endpoint():
    assert {(item.path, method) for item in route.router.routes for method in item.methods} == {
        ("/api/stop-audit", "GET"), ("/api/stop-audit", "POST"),
    }
