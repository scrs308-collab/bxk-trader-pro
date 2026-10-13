"""Real row-lock races, opt-in only, using synthetic accounts in a private schema.

Set BXK_TEST_POSTGRES_URL to a localhost PostgreSQL test database, for example
postgresql://bxk:bxk_test_password@localhost:5432/bxk_test. DATABASE_URL is never
used. No mail is sent, and only a randomly named test schema is created/dropped.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
from threading import Event
import time
import uuid

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models.setup_invitation import SetupInvitation
from bxk_app.db_models.user import User, UserRole
from bxk_app.services import setup_invitation_service as invitations
from bxk_app.services.system_settings_service import hash_app_password, verify_app_password


NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
OLD_TOKEN = "A" * 43
NEW_TOKEN = "B" * 43
INITIAL_PASSWORD = "Synthetic-initial-password-123!"
FIRST_PASSWORD = "Synthetic-first-password-123!"
SECOND_PASSWORD = "Synthetic-second-password-123!"


def _safe_test_url(value):
    """Validate before connecting; query parameters can override the URL host."""
    try:
        url = make_url(value)
    except Exception:
        raise ValueError("BXK_TEST_POSTGRES_URL must be a local PostgreSQL test database URL.") from None
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg"}
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or not re.fullmatch(r"(?:test_[a-z0-9_]+|[a-z0-9_]+_test(?:_[a-z0-9_]+)?)", url.database or "")
        or url.query
    ):
        raise ValueError(
            "Refusing PostgreSQL tests: use localhost and an explicitly test-named "
            "database (such as bxk_test), without URL query parameters."
        )
    return url.set(drivername="postgresql+psycopg")


@pytest.mark.parametrize("url", [
    "postgresql://bxk@db.example.invalid/bxk_test",
    "postgresql://bxk@localhost/bxk_production",
    "postgresql://bxk@localhost/contest",
    "postgresql://bxk@localhost/postgres",
    "postgresql://bxk@localhost/bxk_test?host=db.example.invalid",
    "postgresql://bxk@localhost/bxk_test?service=production",
    "postgresql:///bxk_test",
    "sqlite:///bxk_test",
])
def test_postgres_guard_rejects_unsafe_targets_without_connecting(url):
    with pytest.raises(ValueError):
        _safe_test_url(url)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_postgres_guard_accepts_explicit_local_test_database(host):
    url = _safe_test_url(f"postgresql://bxk:synthetic@{host}:5432/bxk_test")
    assert url.drivername == "postgresql+psycopg"
    assert url.database == "bxk_test"


def _local_connect_args(url):
    # libpq's PGHOSTADDR bypasses DNS and can override a localhost URL. Pin the
    # transport address explicitly for both schema administration and tests.
    return {
        "connect_timeout": 5,
        "hostaddr": "::1" if url.host == "::1" else "127.0.0.1",
    }


@pytest.mark.parametrize("host,expected_address", [
    ("localhost", "127.0.0.1"),
    ("127.0.0.1", "127.0.0.1"),
    ("[::1]", "::1"),
])
def test_postgres_transport_address_overrides_environment(monkeypatch, host, expected_address):
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.1")
    url = _safe_test_url(f"postgresql://bxk:synthetic@{host}:5432/bxk_test")
    assert _local_connect_args(url)["hostaddr"] == expected_address


@pytest.fixture
def postgres_factory():
    value = os.environ.get("BXK_TEST_POSTGRES_URL")
    if not value:
        pytest.skip("Set BXK_TEST_POSTGRES_URL to run isolated PostgreSQL concurrency tests.")
    url = _safe_test_url(value)
    schema = f"bxk_setup_test_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, connect_args=_local_connect_args(url))
    engine = None
    created = False
    try:
        with admin_engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        engine = create_engine(url, connect_args={
            **_local_connect_args(url),
            "options": f"-csearch_path={schema} -clock_timeout=10000 -cstatement_timeout=15000",
        })
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
        Base.metadata.create_all(engine, tables=[User.__table__, SetupInvitation.__table__])
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def invited_user(postgres_factory, monkeypatch):
    # Provider and token generation are always replaced before issuing anything.
    delivered = []
    tokens = iter([OLD_TOKEN, NEW_TOKEN])
    monkeypatch.setattr(config, "BXK_PUBLIC_APP_URL", "https://setup.example.invalid")
    monkeypatch.setattr(invitations.secrets, "token_urlsafe", lambda size: next(tokens))

    def fake_mail(recipient, **message):
        assert recipient == "postgres-race@example.invalid"
        delivered.append(message)

    monkeypatch.setattr(invitations, "send_setup_invitation_email", fake_mail)
    with postgres_factory() as session:
        user = User(
            username="postgres-race", email="postgres-race@example.invalid",
            password_hash=hash_app_password(INITIAL_PASSWORD), role=UserRole.BETA,
            is_active=True, must_change_password=True,
        )
        session.add(user)
        session.commit()
        user_id = user.id
        initial_hash = user.password_hash
        result = invitations.issue_setup_invitation(
            session, user_id=str(user_id), expected_email=user.email,
            expected_username=user.username, now=NOW - timedelta(minutes=2),
        )
        assert result["status"] == "ACCEPTED"
    return user_id, initial_hash, delivered


def _run_contended_actions(factory, holder_action, contender_action):
    """Pause the first actual row lock; prove the other backend waits on it."""
    engine = factory.kw["bind"]
    holder_locked = Event()
    contender_attempted = Event()
    release_holder = Event()
    backend_ids = {}

    def is_user_lock(statement):
        return "FOR UPDATE" in statement.upper() and "users" in statement.lower()

    def before_cursor_execute(connection, cursor, statement, parameters, context, executemany):
        if connection.info.get("invitation_race_role") == "contender" and is_user_lock(statement):
            contender_attempted.set()

    def after_cursor_execute(connection, cursor, statement, parameters, context, executemany):
        if connection.info.get("invitation_race_role") == "holder" and is_user_lock(statement):
            holder_locked.set()
            assert release_holder.wait(10), "The test did not release the first user row lock."

    def run(role, action):
        with factory() as session:
            connection = session.connection()
            connection_info = connection.info
            connection_info["invitation_race_role"] = role
            backend_ids[role] = session.scalar(text("SELECT pg_backend_pid()"))
            try:
                return action(session)
            except ValueError as error:
                return error
            finally:
                # A service commit closes its SQLAlchemy Connection wrapper.
                connection_info.pop("invitation_race_role", None)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(run, "holder", holder_action)
            try:
                assert holder_locked.wait(10), "The first action never acquired its user row lock."
                second = executor.submit(run, "contender", contender_action)
                assert contender_attempted.wait(10), "The concurrent action never attempted its user row lock."
                deadline = time.monotonic() + 5
                with engine.connect() as observer:
                    while time.monotonic() < deadline:
                        blocked = observer.scalar(text(
                            "SELECT :holder = ANY(pg_blocking_pids(:contender))"
                        ), backend_ids)
                        if blocked:
                            break
                        time.sleep(0.02)
                    else:
                        pytest.fail("The second PostgreSQL backend never blocked on the first user row lock.")
            finally:
                release_holder.set()
            return first.result(timeout=20), second.result(timeout=20)
    finally:
        release_holder.set()
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)


def _redeem(token, password):
    return lambda session: invitations.redeem_setup_invitation(
        session, token=token, new_password=password, now=NOW,
    )


def _resend(user_id):
    return lambda session: invitations.issue_setup_invitation(
        session, user_id=str(user_id), expected_email="postgres-race@example.invalid",
        expected_username="postgres-race", now=NOW,
    )


def test_postgres_two_redemptions_have_exactly_one_winner(postgres_factory, invited_user):
    user_id, _, delivered = invited_user
    first, second = _run_contended_actions(
        postgres_factory, _redeem(OLD_TOKEN, FIRST_PASSWORD), _redeem(OLD_TOKEN, SECOND_PASSWORD),
    )
    assert first["password_set"] is True
    assert isinstance(second, invitations.InvalidSetupLink)
    with postgres_factory() as session:
        user = session.get(User, user_id)
        invitation = session.get(SetupInvitation, user_id)
        assert verify_app_password(FIRST_PASSWORD, user.password_hash)
        assert not verify_app_password(SECOND_PASSWORD, user.password_hash)
        assert user.session_version == 1
        assert user.must_change_password is False
        assert invitation.consumed_at == NOW
        assert invitation.token_hash == hashlib.sha256(OLD_TOKEN.encode()).hexdigest()
    assert len(delivered) == 1


def test_postgres_redemption_prevents_waiting_resend_for_established_account(postgres_factory, invited_user):
    user_id, _, delivered = invited_user
    redemption, resend = _run_contended_actions(
        postgres_factory, _redeem(OLD_TOKEN, FIRST_PASSWORD), _resend(user_id),
    )
    assert redemption["password_set"] is True
    assert isinstance(resend, ValueError)
    assert "first password" in str(resend)
    with postgres_factory() as session:
        user = session.get(User, user_id)
        invitation = session.get(SetupInvitation, user_id)
        assert verify_app_password(FIRST_PASSWORD, user.password_hash)
        assert user.must_change_password is False
        assert user.session_version == 1
        assert invitation.consumed_at == NOW
        assert invitation.token_hash == hashlib.sha256(OLD_TOKEN.encode()).hexdigest()
    assert len(delivered) == 1  # The waiting resend must not send any new link.


def test_postgres_resend_invalidates_waiting_old_token_without_changing_credentials(postgres_factory, invited_user):
    user_id, initial_hash, delivered = invited_user
    resend, redemption = _run_contended_actions(
        postgres_factory, _resend(user_id), _redeem(OLD_TOKEN, FIRST_PASSWORD),
    )
    assert resend["status"] == "ACCEPTED"
    assert isinstance(redemption, invitations.InvalidSetupLink)
    with postgres_factory() as session:
        user = session.get(User, user_id)
        invitation = session.get(SetupInvitation, user_id)
        assert user.password_hash == initial_hash
        assert user.must_change_password is True
        assert user.session_version == 0
        assert invitation.consumed_at is None
        assert invitation.token_hash == hashlib.sha256(NEW_TOKEN.encode()).hexdigest()
    assert len(delivered) == 2
    assert delivered[-1]["setup_url"].endswith(f"#token={NEW_TOKEN}")

    with postgres_factory() as session:
        assert _redeem(NEW_TOKEN, SECOND_PASSWORD)(session)["password_set"] is True
    with postgres_factory() as session:
        user = session.get(User, user_id)
        assert verify_app_password(SECOND_PASSWORD, user.password_hash)
        assert user.session_version == 1
        assert user.must_change_password is False
