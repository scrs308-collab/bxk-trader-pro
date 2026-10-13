from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models.setup_invitation import SetupInvitation
from bxk_app.db_models.user import User, UserRole
from bxk_app.services import auth_service, user_service
from bxk_app.services.setup_invitation_service import (
    InvalidSetupLink,
    redeem_setup_invitation,
)
from bxk_app.services.system_settings_service import (
    hash_app_password,
    verify_app_password,
)


@pytest.fixture
def database(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(auth_service, "database_configured", lambda: True)
    monkeypatch.setattr(auth_service, "get_session_factory", lambda: factory)
    monkeypatch.setattr(config, "BXK_SESSION_SECRET", "test-session-secret" * 4)
    monkeypatch.setattr(config, "BXK_SESSION_TTL_SECONDS", 3600)
    monkeypatch.setattr(config, "BXK_APP_USERNAME", "test-owner")
    with factory() as session:
        user = User(
            username="test-beta",
            email="test-beta@example.com",
            password_hash=hash_app_password("TemporaryPassword123!"),
            role=UserRole.BETA,
            is_active=True,
            must_change_password=True,
        )
        session.add(user)
        session.commit()
        user_id = user.id
    yield factory, user_id
    engine.dispose()


def signed_payload(payload):
    encoded = auth_service._b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = auth_service._sign_payload(encoded, config.BXK_SESSION_SECRET)
    return f"{encoded}.{signature}"


def old_database_token(user_id):
    return signed_payload({
        "v": 2,
        "sub": str(user_id),
        "iat": 1000,
        "exp": 4600,
        "nonce": "test-old-cookie",
    })


def test_database_token_uses_authoritative_session_version(database):
    factory, user_id = database
    with factory() as session:
        session.get(User, user_id).session_version = 4
        session.commit()

    token = auth_service.create_database_session_token(str(user_id), now=1000)
    payload = json.loads(auth_service._b64decode(token.split(".")[0]))
    assert payload["session_version"] == 4
    assert auth_service.verify_session_token(token, now=1001) is not None


def test_password_change_revokes_all_old_sessions_and_permits_new_login(database):
    factory, user_id = database
    old_tokens = [
        old_database_token(user_id),
        auth_service.create_database_session_token(str(user_id), now=1000),
        auth_service.create_database_session_token(str(user_id), now=1001),
    ]
    for token in old_tokens:
        assert auth_service.verify_session_token(token, now=1002) is not None

    with factory() as session:
        result = user_service.change_user_password(
            session,
            user_id=str(user_id),
            current_password="TemporaryPassword123!",
            new_password="ChosenPassword123!",
        )
        user = session.get(User, user_id)
        assert result["must_change_password"] is False
        assert user.session_version == 1
        assert verify_app_password("ChosenPassword123!", user.password_hash)

    for token in old_tokens:
        assert auth_service.verify_session_token(token, now=1003) is None

    authentication = auth_service.authenticate_database_credentials(
        "test-beta", "ChosenPassword123!"
    )
    assert authentication["authenticated"] is True
    assert authentication["session_version"] == 1
    assert not auth_service.authenticate_database_credentials(
        "test-beta", "TemporaryPassword123!"
    )["authenticated"]
    new_token = auth_service.create_database_session_token(
        str(user_id), expected_session_version=authentication["session_version"],
        now=1003,
    )
    assert auth_service.verify_session_token(new_token, now=1004) is not None


@pytest.mark.parametrize("value", [None, True, False, 0.0, "0", "1", [], {}, -1, 1])
def test_wrong_or_malformed_session_version_is_rejected(database, value):
    _, user_id = database
    token = signed_payload({
        "v": 2, "sub": str(user_id), "iat": 1000, "exp": 4600,
        "session_version": value,
    })
    assert auth_service.verify_session_token(token, now=1001) is None


@pytest.mark.parametrize("payload", [None, [], "invalid", 42])
def test_non_object_payload_is_rejected(database, payload):
    assert auth_service.verify_session_token(signed_payload(payload), now=1001) is None


def test_pre_migration_cookie_only_works_for_unchanged_account(database):
    factory, user_id = database
    token = old_database_token(user_id)
    assert auth_service.verify_session_token(token, now=1001) is not None
    with factory() as session:
        session.get(User, user_id).session_version = 1
        session.commit()
    assert auth_service.verify_session_token(token, now=1002) is None


def test_password_change_between_authentication_and_issuance_is_rejected(database):
    factory, user_id = database
    authentication = auth_service.authenticate_database_credentials(
        "test-beta", "TemporaryPassword123!"
    )
    with factory() as session:
        user_service.change_user_password(
            session, user_id=str(user_id),
            current_password="TemporaryPassword123!",
            new_password="ChosenPassword123!",
        )
    with pytest.raises(ValueError, match="credentials changed"):
        auth_service.create_database_session_token(
            str(user_id),
            expected_session_version=authentication["session_version"],
            now=1001,
        )


@pytest.mark.parametrize("value", [True, False, "0", 0.0, -1, 1])
def test_issuance_rejects_invalid_or_stale_expected_version(database, value):
    _, user_id = database
    with pytest.raises(ValueError, match="credentials changed"):
        auth_service.create_database_session_token(
            str(user_id), expected_session_version=value, now=1000
        )


def test_issuance_rejects_missing_and_inactive_users(database):
    factory, user_id = database
    with pytest.raises(ValueError, match="user is unavailable"):
        auth_service.create_database_session_token(str(uuid.uuid4()), now=1000)
    with factory() as session:
        session.get(User, user_id).is_active = False
        session.commit()
    with pytest.raises(ValueError, match="user is unavailable"):
        auth_service.create_database_session_token(str(user_id), now=1000)


def test_issuance_rejects_unconfigured_database(database, monkeypatch):
    _, user_id = database
    monkeypatch.setattr(auth_service, "database_configured", lambda: False)
    with pytest.raises(ValueError, match="authentication is unavailable"):
        auth_service.create_database_session_token(str(user_id), now=1000)


def test_failed_change_preserves_password_and_session_version(database):
    factory, user_id = database
    with factory() as session:
        old_hash = session.get(User, user_id).password_hash
        with pytest.raises(ValueError, match="Current password is incorrect"):
            user_service.change_user_password(
                session, user_id=str(user_id), current_password="WrongPassword!",
                new_password="ChosenPassword123!",
            )
        session.expire_all()
        user = session.get(User, user_id)
        assert user.session_version == 0
        assert user.password_hash == old_hash
        assert user.must_change_password is True


def test_concurrent_credential_change_cannot_be_overwritten(database, monkeypatch):
    factory, user_id = database
    concurrent_hash = hash_app_password("ConcurrentPassword123!")

    def concurrent_change_then_hash(password):
        with factory() as competing_session:
            competing_user = competing_session.get(User, user_id)
            competing_user.password_hash = concurrent_hash
            competing_user.session_version += 1
            competing_user.must_change_password = False
            competing_session.commit()
        return hash_app_password(password)

    monkeypatch.setattr(user_service, "hash_app_password", concurrent_change_then_hash)
    with factory() as session:
        with pytest.raises(ValueError, match="credentials changed"):
            user_service.change_user_password(
                session, user_id=str(user_id),
                current_password="TemporaryPassword123!",
                new_password="ChosenPassword123!",
            )
    with factory() as session:
        user = session.get(User, user_id)
        assert user.password_hash == concurrent_hash
        assert user.session_version == 1


def test_legacy_owner_session_is_unchanged(database):
    token = auth_service.create_session_token("test-owner", now=1000)
    result = auth_service.verify_session_token(token, now=1001)
    assert result["auth_source"] == "CONFIG"
    assert result["role"] == "OWNER"


def add_dummy_invitation(factory, user_id):
    token = "s" * 43
    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add(SetupInvitation(
            user_id=user_id,
            token_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
            recipient_email="test-beta@example.com",
            credential_version=0,
            created_at=now,
            expires_at=now + timedelta(hours=24),
            delivery_status="ACCEPTED",
        ))
        session.commit()
    return token


def test_password_change_permanently_invalidates_outstanding_setup_link(database):
    factory, user_id = database
    token = add_dummy_invitation(factory, user_id)
    with factory() as session:
        user_service.change_user_password(
            session, user_id=str(user_id),
            current_password="TemporaryPassword123!",
            new_password="ChosenPassword123!",
        )
        # Even if the account is later marked for setup again, an older
        # invitation cannot replace a newer password revision.
        session.get(User, user_id).must_change_password = True
        session.commit()
    with factory() as session:
        with pytest.raises(InvalidSetupLink):
            redeem_setup_invitation(
                session, token=token, new_password="ReplayedPassword123!"
            )
        user = session.get(User, user_id)
        assert user.session_version == 1
        assert verify_app_password("ChosenPassword123!", user.password_hash)


def test_setup_redemption_revokes_temporary_password_sessions(database):
    factory, user_id = database
    setup_token = add_dummy_invitation(factory, user_id)
    old_tokens = [
        old_database_token(user_id),
        auth_service.create_database_session_token(str(user_id), now=1000),
    ]
    with factory() as session:
        redeem_setup_invitation(
            session, token=setup_token, new_password="ChosenPassword123!"
        )
    for token in old_tokens:
        assert auth_service.verify_session_token(token, now=1001) is None
    authentication = auth_service.authenticate_database_credentials(
        "test-beta", "ChosenPassword123!"
    )
    assert authentication["authenticated"] is True
    assert authentication["session_version"] == 1
    fresh_token = auth_service.create_database_session_token(
        str(user_id), expected_session_version=authentication["session_version"],
        now=1001,
    )
    assert auth_service.verify_session_token(fresh_token, now=1002) is not None
