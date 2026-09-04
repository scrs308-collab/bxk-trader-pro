import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import Base, get_db
from bxk_app.db_models.broker_connection import (
    BrokerConnection,
)
from bxk_app.db_models.user import User, UserRole
from bxk_app.main import app
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import (
    hash_app_password,
)


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def configure_auth(
    monkeypatch,
    session_factory,
):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        True,
    )

    monkeypatch.setattr(
        config,
        "BXK_SESSION_SECRET",
        "a" * 64,
    )

    monkeypatch.setattr(
        config,
        "BXK_SESSION_TTL_SECONDS",
        3600,
    )

    monkeypatch.setattr(
        config,
        "BXK_AUTH_COOKIE_SECURE",
        False,
    )

    monkeypatch.setattr(
        auth_service,
        "database_configured",
        lambda: True,
    )

    monkeypatch.setattr(
        auth_service,
        "get_session_factory",
        lambda: session_factory,
    )

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[
        get_db
    ] = override_get_db


def add_user(
    session_factory,
    *,
    username,
    email,
    role,
):
    with session_factory() as session:
        user = User(
            username=username,
            email=email,
            password_hash=hash_app_password(
                "Password123!"
            ),
            role=role,
            is_active=True,
            must_change_password=False,
        )

        session.add(user)
        session.commit()

        return str(user.id)


def client_with_user(
    user_id,
):
    client = TestClient(app)

    token = (
        auth_service
        .create_database_session_token(
            user_id
        )
    )

    client.cookies.set(
        auth_service.SESSION_COOKIE_NAME,
        token,
    )

    return client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_admin_users_requires_authentication(
    monkeypatch,
):
    factory = make_session_factory()

    configure_auth(
        monkeypatch,
        factory,
    )

    client = TestClient(app)

    response = client.get(
        "/api/admin/users"
    )

    assert response.status_code == 401


def test_beta_cannot_list_admin_users(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta1",
        email="beta1@example.com",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        beta_id
    )

    response = client.get(
        "/api/admin/users"
    )

    assert response.status_code == 403


def test_owner_can_list_admin_users(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner",
        email="owner@example.com",
        role=UserRole.OWNER,
    )

    add_user(
        factory,
        username="beta1",
        email="beta1@example.com",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        owner_id
    )

    response = client.get(
        "/api/admin/users"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["users"]) == 2

    for user in body["users"]:
        assert "password_hash" not in user


def test_owner_can_create_beta_user(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner",
        email="owner@example.com",
        role=UserRole.OWNER,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        owner_id
    )

    response = client.post(
        "/api/admin/users",
        json={
            "username": "newbeta",
            "email": "newbeta@example.com",
            "role": "BETA",
            "temporary_password":
                "Temporary123!",
        },
    )

    assert response.status_code == 201

    user = response.json()["user"]

    assert user["username"] == "newbeta"
    assert user["role"] == "BETA"
    assert user["is_active"] is True
    assert (
        user["must_change_password"]
        is True
    )
    assert "password_hash" not in user


def test_beta_cannot_create_user(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta1",
        email="beta1@example.com",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        beta_id
    )

    response = client.post(
        "/api/admin/users",
        json={
            "username": "beta2",
            "email": "beta2@example.com",
            "role": "BETA",
            "temporary_password":
                "Temporary123!",
        },
    )

    assert response.status_code == 403


def test_admin_api_rejects_owner_creation(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner",
        email="owner@example.com",
        role=UserRole.OWNER,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        owner_id
    )

    response = client.post(
        "/api/admin/users",
        json={
            "username": "owner2",
            "email": "owner2@example.com",
            "role": "OWNER",
            "temporary_password":
                "Temporary123!",
        },
    )

    assert response.status_code == 422

def test_owner_can_disable_beta_and_existing_session_dies(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner",
        email="owner@example.com",
        role=UserRole.OWNER,
    )

    beta_id = add_user(
        factory,
        username="beta1",
        email="beta1@example.com",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    owner_client = client_with_user(
        owner_id
    )

    beta_client = client_with_user(
        beta_id
    )

    before = beta_client.get(
        "/api/auth/status"
    )

    assert before.status_code == 200
    assert (
        before.json()["authenticated"]
        is True
    )

    response = owner_client.patch(
        f"/api/admin/users/{beta_id}/status",
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 200

    user = response.json()["user"]

    assert user["id"] == beta_id
    assert user["is_active"] is False
    assert "password_hash" not in user

    after = beta_client.get(
        "/api/auth/status"
    )

    assert after.status_code == 200
    assert (
        after.json()["authenticated"]
        is False
    )


def test_beta_cannot_change_user_status(
    monkeypatch,
):
    factory = make_session_factory()

    beta1_id = add_user(
        factory,
        username="beta1",
        email="beta1@example.com",
        role=UserRole.BETA,
    )

    beta2_id = add_user(
        factory,
        username="beta2",
        email="beta2@example.com",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        beta1_id
    )

    response = client.patch(
        f"/api/admin/users/{beta2_id}/status",
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 403


def test_owner_cannot_disable_owner_account(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner",
        email="owner@example.com",
        role=UserRole.OWNER,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        owner_id
    )

    response = client.patch(
        f"/api/admin/users/{owner_id}/status",
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 422

    assert (
        "OWNER accounts"
        in response.json()["detail"]
    )


def test_admin_status_update_returns_404_for_missing_user(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner",
        email="owner@example.com",
        role=UserRole.OWNER,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        owner_id
    )

    missing_id = str(
        uuid.uuid4()
    )

    response = client.patch(
        f"/api/admin/users/{missing_id}/status",
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 404


def test_owner_can_enable_beta_broker_live_trading(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner_live",
        email="owner_live@example.com",
        role=UserRole.OWNER,
    )

    beta_id = add_user(
        factory,
        username="beta_live",
        email="beta_live@example.com",
        role=UserRole.BETA,
    )

    with factory() as session:
        connection = BrokerConnection(
            user_id=uuid.UUID(
                beta_id
            ),
            broker="tastytrade",
            client_secret_encrypted="encrypted-secret",
            refresh_token_encrypted="encrypted-refresh",
            account_number="BETA1234",
            is_active=True,
            is_verified=True,
            live_trading_enabled=False,
        )

        session.add(
            connection
        )
        session.commit()

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        owner_id
    )

    response = client.patch(
        (
            f"/api/admin/users/{beta_id}"
            "/broker-live-trading"
        ),
        json={
            "enabled": True,
        },
    )

    assert response.status_code == 200

    broker_status = (
        response.json()["broker"]
    )

    assert (
        broker_status[
            "live_trading_enabled"
        ]
        is True
    )

    assert (
        broker_status["user_id"]
        == beta_id
    )

    with factory() as session:
        connection = session.scalar(
            select(
                BrokerConnection
            ).where(
                BrokerConnection.user_id
                == uuid.UUID(beta_id)
            )
        )

        assert connection is not None

        assert (
            connection.live_trading_enabled
            is True
        )


def test_beta_cannot_enable_broker_live_trading(
    monkeypatch,
):
    factory = make_session_factory()

    beta1_id = add_user(
        factory,
        username="beta_live_1",
        email="beta_live_1@example.com",
        role=UserRole.BETA,
    )

    beta2_id = add_user(
        factory,
        username="beta_live_2",
        email="beta_live_2@example.com",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        beta1_id
    )

    response = client.patch(
        (
            f"/api/admin/users/{beta2_id}"
            "/broker-live-trading"
        ),
        json={
            "enabled": True,
        },
    )

    assert response.status_code == 403


def test_admin_live_trading_requires_broker_connection(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner_no_broker",
        email="owner_no_broker@example.com",
        role=UserRole.OWNER,
    )

    beta_id = add_user(
        factory,
        username="beta_no_broker",
        email="beta_no_broker@example.com",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(
        owner_id
    )

    response = client.patch(
        (
            f"/api/admin/users/{beta_id}"
            "/broker-live-trading"
        ),
        json={
            "enabled": True,
        },
    )

    assert response.status_code == 404

    assert (
        "Tastytrade connection"
        in response.json()["detail"]
    )

