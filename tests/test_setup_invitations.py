"""Synthetic-data invitation tests; no provider or production account calls."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import urllib.error
from unittest.mock import Mock
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import Base, get_db
from bxk_app.db_models.user import User, UserRole
from bxk_app.db_models.setup_invitation import SetupInvitation
from bxk_app.main import app
from bxk_app.services import auth_service, setup_invitation_service as service
from bxk_app.services.system_settings_service import hash_app_password, verify_app_password

NOW = datetime(2026, 10, 13, 19, 0, tzinfo=timezone.utc)
ORIGIN = "https://app.bxktraderpro.com"
DUMMY_PASSWORD = "SyntheticSetupOnly123!"


@pytest.fixture
def ctx(monkeypatch):
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        owner = User(username="synthetic-owner", email="owner@example.com", role=UserRole.OWNER,
                     password_hash=hash_app_password(DUMMY_PASSWORD), is_active=True, must_change_password=False)
        target = User(username="synthetic-new-user", email="new@example.com", role=UserRole.BETA,
                      password_hash=hash_app_password(DUMMY_PASSWORD), is_active=True, must_change_password=True)
        session.add_all([owner, target]); session.commit()
        owner_id, user_id = str(owner.id), str(target.id)
    monkeypatch.setattr(config, "BXK_PUBLIC_APP_URL", ORIGIN)
    monkeypatch.setattr(config, "BXK_AUTH_ENABLED", True)
    monkeypatch.setattr(config, "BXK_SESSION_SECRET", "test-only-not-production" * 4)
    monkeypatch.setattr(config, "BXK_AUTH_COOKIE_SECURE", False)
    monkeypatch.setattr(auth_service, "database_configured", lambda: True)
    monkeypatch.setattr(auth_service, "get_session_factory", lambda: factory)
    mail = Mock(return_value=True)
    monkeypatch.setattr(service, "send_setup_invitation_email", mail)
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = db
    yield factory, owner_id, user_id, mail
    app.dependency_overrides.clear()
    engine.dispose()


def issue(ctx, now=NOW):
    factory, owner_id, user_id, mail = ctx
    with factory() as session:
        result = service.issue_setup_invitation(session, user_id=user_id, owner_id=owner_id,
            expected_email="new@example.com", expected_username="synthetic-new-user", now=now)
    token = mail.call_args.kwargs["setup_url"].split("#token=", 1)[1]
    return result, token


def test_setup_is_explicit_and_never_stores_or_returns_token(ctx):
    factory, owner_id, user_id, mail = ctx
    with factory() as session:
        assert session.get(SetupInvitation, uuid.UUID(user_id)) is None
    result, token = issue(ctx)
    assert result["status"] == "ACCEPTED"
    assert "not confirmed" in result["message"]
    assert token not in json.dumps(result)
    assert mail.call_args.args == ("new@example.com",)
    assert mail.call_args.kwargs["setup_url"].startswith(ORIGIN + "/setup-password#token=")
    with factory() as session:
        invite = session.get(SetupInvitation, uuid.UUID(user_id))
        assert invite.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert invite.token_hash != token
        assert invite.requested_by == uuid.UUID(owner_id)
        user = session.get(User, uuid.UUID(user_id))
        assert user.must_change_password
        assert user.session_version == 0
        assert verify_app_password(DUMMY_PASSWORD, user.password_hash)


def test_redeem_once_sets_password_and_revokes_sessions(ctx):
    factory, _, user_id, _ = ctx
    _, token = issue(ctx)
    old_session = auth_service.create_database_session_token(user_id)
    with factory() as session:
        result = service.redeem_setup_invitation(session, token=token, new_password="SyntheticNewPassword123!", now=NOW)
        assert result["password_set"] is True
    assert auth_service.verify_session_token(old_session) is None
    with factory() as session:
        user = session.get(User, uuid.UUID(user_id))
        assert not user.must_change_password and user.session_version == 1
        assert verify_app_password("SyntheticNewPassword123!", user.password_hash)
        assert not verify_app_password(DUMMY_PASSWORD, user.password_hash)
        assert user.role == UserRole.BETA and user.is_active
        assert not user.broker_oauth_enabled
        with pytest.raises(service.InvalidSetupLink):
            service.redeem_setup_invitation(session, token=token, new_password="AnotherSyntheticPassword!", now=NOW)
    fresh = auth_service.create_database_session_token(user_id)
    assert auth_service.verify_session_token(fresh)["user_id"] == user_id


@pytest.mark.parametrize("field,value", [("role", UserRole.OWNER), ("must_change_password", False), ("is_active", False)])
def test_ineligible_accounts_never_receive_invites(ctx, field, value):
    factory, _, user_id, mail = ctx
    with factory() as session:
        user = session.get(User, uuid.UUID(user_id)); setattr(user, field, value); session.commit()
    with pytest.raises(ValueError):
        issue(ctx)
    mail.assert_not_called()
    with factory() as session:
        assert session.get(SetupInvitation, uuid.UUID(user_id)) is None


@pytest.mark.parametrize("change", ["email", "password", "disabled", "owner", "established"])
def test_account_changes_make_existing_link_invalid(ctx, change):
    factory, _, user_id, _ = ctx
    _, token = issue(ctx)
    with factory() as session:
        user = session.get(User, uuid.UUID(user_id))
        if change == "email": user.email = "changed@example.com"
        if change == "password": user.session_version += 1
        if change == "disabled": user.is_active = False
        if change == "owner": user.role = UserRole.OWNER
        if change == "established": user.must_change_password = False
        session.commit()
        with pytest.raises(service.InvalidSetupLink):
            service.redeem_setup_invitation(session, token=token, new_password="AnotherSyntheticPassword!", now=NOW)
        assert session.get(SetupInvitation, user.id).consumed_at is None


def test_reviewed_identity_must_still_match(ctx):
    factory, owner_id, user_id, mail = ctx
    with factory() as session:
        with pytest.raises(ValueError, match="changed since"):
            service.issue_setup_invitation(session, user_id=user_id, owner_id=owner_id,
                expected_email="someone-else@example.com", expected_username="synthetic-new-user", now=NOW)
    mail.assert_not_called()


@pytest.mark.parametrize("offset", [timedelta(hours=24), timedelta(days=2)])
def test_exact_expiry_and_later_rejected(ctx, offset):
    factory, _, _, _ = ctx
    _, token = issue(ctx)
    with factory() as session:
        with pytest.raises(service.InvalidSetupLink):
            service.redeem_setup_invitation(session, token=token, new_password="AnotherSyntheticPassword!", now=NOW + offset)


def test_resend_cooldown_rotates_link_without_resetting_password(ctx):
    factory, _, user_id, mail = ctx
    _, old = issue(ctx)
    with pytest.raises(service.InvitationCooldown): issue(ctx, NOW + timedelta(seconds=59))
    assert mail.call_count == 1
    _, new = issue(ctx, NOW + timedelta(seconds=60))
    assert new != old and mail.call_count == 2
    with factory() as session:
        with pytest.raises(service.InvalidSetupLink):
            service.redeem_setup_invitation(session, token=old, new_password="AnotherSyntheticPassword!", now=NOW + timedelta(seconds=61))
        user = session.get(User, uuid.UUID(user_id))
        assert verify_app_password(DUMMY_PASSWORD, user.password_hash)
        assert user.session_version == 0
        service.redeem_setup_invitation(session, token=new, new_password="AnotherSyntheticPassword!", now=NOW + timedelta(seconds=61))


@pytest.mark.parametrize("password", ["short", "x" * 1025])
def test_bad_password_does_not_consume_link(ctx, password):
    factory, _, user_id, _ = ctx
    _, token = issue(ctx)
    with factory() as session:
        with pytest.raises(ValueError):
            service.redeem_setup_invitation(session, token=token, new_password=password, now=NOW)
        assert session.get(SetupInvitation, uuid.UUID(user_id)).consumed_at is None
        service.redeem_setup_invitation(session, token=token, new_password="AnotherSyntheticPassword!", now=NOW)


@pytest.mark.parametrize("kind,expected", [("local", "FAILED"), ("rejected", "FAILED"), ("timeout", "UNKNOWN"), ("server", "UNKNOWN")])
def test_provider_status_is_honest(ctx, kind, expected):
    _, _, _, mail = ctx
    def fail(*args, **kwargs):
        if kind == "timeout": raise TimeoutError("synthetic timeout")
        if kind == "local": raise RuntimeError("not configured")
        cause = urllib.error.HTTPError("https://example.com", 422 if kind == "rejected" else 503, "synthetic", {}, None)
        raise RuntimeError("synthetic failure") from cause
    mail.side_effect = fail
    result, token = issue(ctx)
    assert result["status"] == expected
    assert token not in json.dumps(result)


@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "https://example.com/path", "https://example.com?next=evil", "https://example.com/#fragment", ""])
def test_untrusted_link_origin_rejected_before_send(ctx, monkeypatch, url):
    monkeypatch.setattr(config, "BXK_PUBLIC_APP_URL", url)
    with pytest.raises(ValueError): issue(ctx)
    ctx[3].assert_not_called()


def owner_client(ctx):
    client = TestClient(app)
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, auth_service.create_database_session_token(ctx[1]))
    return client


def test_owner_route_requires_reviewed_identity_and_same_origin(ctx):
    client = owner_client(ctx)
    path = f"/api/admin/users/{ctx[2]}/setup-invitation"
    body = {"expected_email": "new@example.com", "expected_username": "synthetic-new-user"}
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    response = client.post(path, json=body, headers={"Origin": ORIGIN})
    assert response.status_code == 200
    data = response.json()
    assert data["invitation"]["status"] == "ACCEPTED"
    assert data["user"]["setup_invitation_eligible"] is True
    assert data["user"]["setup_invitation"]["status"] == "ACCEPTED"
    assert "token" not in response.text and "password_hash" not in response.text
    assert client.post(path, json=body, headers={"Origin": ORIGIN}).status_code == 429
    assert ctx[3].call_count == 1


def test_nonowner_cannot_issue(ctx):
    factory, _, user_id, mail = ctx
    client = TestClient(app)
    path = f"/api/admin/users/{user_id}/setup-invitation"
    body = {"expected_email": "new@example.com", "expected_username": "synthetic-new-user"}
    assert client.post(path, json=body, headers={"Origin": ORIGIN}).status_code == 401
    with factory() as session:
        user = session.get(User, uuid.UUID(user_id)); user.must_change_password = False; session.commit()
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, auth_service.create_database_session_token(user_id))
    assert client.post(path, json=body, headers={"Origin": ORIGIN}).status_code == 403
    mail.assert_not_called()


def test_public_setup_requires_token_no_session_created_and_no_secret_echo(ctx):
    result, token = issue(ctx, datetime.now(timezone.utc))
    client = TestClient(app)
    response = client.get("/setup-password")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    # Merely visiting/scanning the page does not consume anything.
    with ctx[0]() as session:
        assert session.get(SetupInvitation, uuid.UUID(ctx[2])).consumed_at is None
    for payload in [{"token": token}, {"token": {"secret": token}, "new_password": "SyntheticPassword!"}]:
        bad = client.post("/api/auth/setup-password", json=payload, headers={"Origin": ORIGIN})
        assert bad.status_code == 422
        assert token not in bad.text and "SyntheticPassword" not in bad.text
    response = client.post("/api/auth/setup-password", json={"token": token, "new_password": "SyntheticNewPassword!"}, headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert token not in response.text and "SyntheticNewPassword" not in response.text
    again = client.post("/api/auth/setup-password", json={"token": token, "new_password": "SyntheticNextPassword!"}, headers={"Origin": ORIGIN})
    assert again.status_code == 400 and again.json()["code"] == "INVALID_SETUP_LINK"
    assert token not in again.text


def test_database_failure_rolls_back_password_and_consumption(ctx, monkeypatch):
    factory, _, user_id, _ = ctx
    _, token = issue(ctx)
    with factory() as session:
        monkeypatch.setattr(session, "commit", Mock(side_effect=RuntimeError("synthetic commit failure")))
        with pytest.raises(RuntimeError):
            service.redeem_setup_invitation(session, token=token, new_password="SyntheticNewPassword!", now=NOW)
        session.rollback()
    with factory() as session:
        user = session.get(User, uuid.UUID(user_id))
        assert user.must_change_password and user.session_version == 0
        assert verify_app_password(DUMMY_PASSWORD, user.password_hash)
        assert session.get(SetupInvitation, user.id).consumed_at is None
