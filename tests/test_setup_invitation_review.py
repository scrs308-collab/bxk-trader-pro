"""Independent adversarial checks; synthetic accounts and intercepted mail only."""
import json
import urllib.error
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from bxk_app.database import get_db
from bxk_app.db_models.setup_invitation import SetupInvitation
from bxk_app.db_models.user import User, UserRole
from bxk_app.main import app
from bxk_app.services import email_service
from bxk_app.services import setup_invitation_service as service
from bxk_app.services.system_settings_service import verify_app_password
from test_setup_invitations import (
    DUMMY_PASSWORD, NOW, ORIGIN, ctx, issue, owner_client,
)


DUMMY_TOKEN = "r" * 43


@pytest.mark.parametrize("kind,expected", [
    ("accepted", "ACCEPTED"),
    ("missing_key", "FAILED"),
    ("rejected", "FAILED"),
    ("rate_limited", "FAILED"),
    ("server", "UNKNOWN"),
    ("network", "UNKNOWN"),
    ("timeout", "UNKNOWN"),
])
def test_real_email_helper_transport_classification(ctx, monkeypatch, caplog, kind, expected):
    """Exercise the actual helper's exception wrapping, without a network call."""
    monkeypatch.setattr(service, "send_setup_invitation_email", email_service.send_setup_invitation_email)
    monkeypatch.setattr(service.secrets, "token_urlsafe", lambda size: DUMMY_TOKEN)
    monkeypatch.setattr(email_service, "_resend_api_key", lambda: "" if kind == "missing_key" else "dummy-test-key")
    monkeypatch.setenv("BXK_SMTP_FROM", "security@example.test")
    transport = Mock()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", transport)
    if kind == "accepted":
        response = Mock(status=200)
        transport.return_value.__enter__ = Mock(return_value=response)
        transport.return_value.__exit__ = Mock(return_value=False)
    elif kind in {"rejected", "rate_limited", "server"}:
        code = {"rejected": 422, "rate_limited": 429, "server": 503}[kind]
        transport.side_effect = urllib.error.HTTPError(
            "https://example.test", code, f"Synthetic error {DUMMY_TOKEN}", {}, None,
        )
    elif kind == "network":
        transport.side_effect = urllib.error.URLError(f"Synthetic network error {DUMMY_TOKEN}")
    elif kind == "timeout":
        transport.side_effect = TimeoutError(f"Synthetic timeout {DUMMY_TOKEN}")

    factory, owner_id, user_id, _ = ctx
    with factory() as session:
        result = service.issue_setup_invitation(
            session, user_id=user_id, owner_id=owner_id,
            expected_email="new@example.com", expected_username="synthetic-new-user", now=NOW,
        )
    assert result["status"] == expected
    assert DUMMY_TOKEN not in json.dumps(result)
    assert DUMMY_TOKEN not in caplog.text
    if kind == "missing_key":
        transport.assert_not_called()
    else:
        transport.assert_called_once()
        request = transport.call_args.args[0]
        payload = json.loads(request.data)
        assert payload["to"] == ["new@example.com"]
        assert ORIGIN + "/setup-password#token=" + DUMMY_TOKEN in payload["text"]
        assert DUMMY_PASSWORD not in payload["text"]


@pytest.mark.parametrize("status,exception,can_redeem", [
    ("FAILED", RuntimeError("synthetic missing mail configuration"), False),
    ("UNKNOWN", TimeoutError("synthetic response timeout"), True),
])
def test_failed_link_rejected_but_uncertain_delivery_remains_redeemable(ctx, status, exception, can_redeem):
    factory, _, user_id, mail = ctx
    mail.side_effect = exception
    result, token = issue(ctx)
    assert result["status"] == status
    with factory() as session:
        if can_redeem:
            result = service.redeem_setup_invitation(
                session, token=token, new_password="SyntheticChosenPassword!", now=NOW,
            )
            assert result["password_set"] is True
        else:
            with pytest.raises(service.InvalidSetupLink):
                service.redeem_setup_invitation(
                    session, token=token, new_password="SyntheticChosenPassword!", now=NOW,
                )
            user = session.get(User, uuid.UUID(user_id))
            assert user.must_change_password and user.session_version == 0
            assert verify_app_password(DUMMY_PASSWORD, user.password_hash)
            assert session.get(SetupInvitation, user.id).consumed_at is None


def test_viewer_can_finish_setup_without_broker_or_role_changes(ctx):
    factory, _, user_id, _ = ctx
    with factory() as session:
        user = session.get(User, uuid.UUID(user_id))
        user.role = UserRole.VIEWER
        session.commit()
    _, token = issue(ctx)
    with factory() as session:
        service.redeem_setup_invitation(
            session, token=token, new_password="SyntheticViewerPassword!", now=NOW,
        )
    with factory() as session:
        user = session.get(User, uuid.UUID(user_id))
        assert user.role == UserRole.VIEWER
        assert user.is_active and not user.broker_oauth_enabled
        assert not user.must_change_password and user.session_version == 1


@pytest.mark.parametrize("origin", [None, "https://untrusted.example", "null"])
def test_public_setup_rejects_missing_or_cross_origin_without_consuming(ctx, origin):
    _, token = issue(ctx)
    headers = {} if origin is None else {"Origin": origin}
    response = TestClient(app).post(
        "/api/auth/setup-password", headers=headers,
        json={"token": token, "new_password": "SyntheticChosenPassword!"},
    )
    assert response.status_code == 403
    assert token not in response.text and "SyntheticChosenPassword" not in response.text
    assert response.headers["cache-control"] == "no-store"
    with ctx[0]() as session:
        user = session.get(User, uuid.UUID(ctx[2]))
        assert user.must_change_password and user.session_version == 0
        assert session.get(SetupInvitation, user.id).consumed_at is None


def test_reviewed_username_must_match_as_well_as_email(ctx):
    factory, owner_id, user_id, mail = ctx
    with factory() as session:
        with pytest.raises(ValueError, match="changed since"):
            service.issue_setup_invitation(
                session, user_id=user_id, owner_id=owner_id,
                expected_email="new@example.com", expected_username="different-reviewed-user", now=NOW,
            )
    mail.assert_not_called()


@pytest.mark.parametrize("failed_commit", [1, 2])
def test_issue_commit_failures_are_uncertain_without_secret_echo_or_resend(ctx, monkeypatch, caplog, failed_commit):
    """Fail before dispatch or after provider acceptance, preserving honest metadata."""
    factory, _, user_id, mail = ctx
    monkeypatch.setattr(service.secrets, "token_urlsafe", lambda size: DUMMY_TOKEN)

    def failing_db():
        with factory() as session:
            original_commit = session.commit
            commits = 0

            def commit():
                nonlocal commits
                commits += 1
                if commits == failed_commit:
                    raise OperationalError(
                        "synthetic statement", {"private": DUMMY_TOKEN},
                        RuntimeError("synthetic database error"),
                    )
                original_commit()

            monkeypatch.setattr(session, "commit", commit)
            yield session

    app.dependency_overrides[get_db] = failing_db
    response = owner_client(ctx).post(
        f"/api/admin/users/{user_id}/setup-invitation", headers={"Origin": ORIGIN},
        json={"expected_email": "new@example.com", "expected_username": "synthetic-new-user"},
    )
    assert response.status_code == 503
    assert "unconfirmed" in response.json()["detail"]
    assert response.headers["cache-control"] == "no-store"
    assert DUMMY_TOKEN not in response.text and DUMMY_TOKEN not in caplog.text
    assert "synthetic statement" not in response.text
    assert mail.call_count == failed_commit - 1
    with factory() as session:
        user = session.get(User, uuid.UUID(user_id))
        assert user.must_change_password and user.session_version == 0
        assert verify_app_password(DUMMY_PASSWORD, user.password_hash)
        invitation = session.get(SetupInvitation, user.id)
        if failed_commit == 1:
            assert invitation is None
        else:
            assert invitation.delivery_status == "DISPATCHING"
            assert service.invitation_metadata(invitation)["status"] == "UNKNOWN"
            assert invitation.consumed_at is None
