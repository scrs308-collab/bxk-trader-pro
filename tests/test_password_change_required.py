from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import (
    Base,
    get_db,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.main import app
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import (
    hash_app_password,
    verify_app_password,
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
    factory,
):
    monkeypatch.setattr(
        config,
        "BXK_APP_USERNAME",
        "owner",
    )

    monkeypatch.setattr(
        config,
        "BXK_APP_PASSWORD_HASH",
        hash_app_password(
            "OwnerPassword123!"
        ),
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
        "BXK_AUTH_ENABLED",
        True,
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
        lambda: factory,
    )

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[
        get_db
    ] = override_get_db


def add_forced_change_user(
    factory,
):
    with factory() as session:
        user = User(
            username="beta1",
            email="beta1@example.com",
            password_hash=hash_app_password(
                "Temporary123!"
            ),
            role=UserRole.BETA,
            is_active=True,
            must_change_password=True,
        )

        session.add(user)
        session.commit()

        return str(user.id)


def test_login_reports_password_change_required(
    monkeypatch,
):
    factory = make_session_factory()

    add_forced_change_user(
        factory
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={
            "username": "beta1",
            "password": "Temporary123!",
        },
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "must_change_password"
        ]
        is True
    )

    app.dependency_overrides.clear()


def test_forced_change_user_is_blocked_from_app(
    monkeypatch,
):
    factory = make_session_factory()

    add_forced_change_user(
        factory
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = TestClient(app)

    client.post(
        "/api/auth/login",
        json={
            "username": "beta1",
            "password": "Temporary123!",
        },
    )

    response = client.get(
        "/",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        response.headers["location"]
        == "/change-password"
    )

    app.dependency_overrides.clear()


def test_forced_change_user_api_access_is_blocked(
    monkeypatch,
):
    factory = make_session_factory()

    add_forced_change_user(
        factory
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = TestClient(app)

    client.post(
        "/api/auth/login",
        json={
            "username": "beta1",
            "password": "Temporary123!",
        },
    )

    response = client.get(
        "/api/admin/users"
    )

    assert response.status_code == 403

    body = response.json()

    assert (
        body["code"]
        == "PASSWORD_CHANGE_REQUIRED"
    )

    app.dependency_overrides.clear()


def test_wrong_current_password_is_rejected(
    monkeypatch,
):
    factory = make_session_factory()

    add_forced_change_user(
        factory
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = TestClient(app)

    client.post(
        "/api/auth/login",
        json={
            "username": "beta1",
            "password": "Temporary123!",
        },
    )

    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "WrongPassword!",
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 422

    app.dependency_overrides.clear()


def test_successful_change_clears_requirement(
    monkeypatch,
):
    factory = make_session_factory()

    user_id = add_forced_change_user(
        factory
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = TestClient(app)

    client.post(
        "/api/auth/login",
        json={
            "username": "beta1",
            "password": "Temporary123!",
        },
    )

    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "Temporary123!",
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 200
    assert (
        response.json()[
            "must_change_password"
        ]
        is False
    )

    import uuid

    with factory() as session:
        user = session.get(
            User,
            uuid.UUID(user_id),
        )

        assert (
            user.must_change_password
            is False
        )

        assert verify_app_password(
            "NewPassword123!",
            user.password_hash,
        )

        assert not verify_app_password(
            "Temporary123!",
            user.password_hash,
        )

    # Existing session should become unrestricted
    # because session verification re-reads the user.
    home = client.get(
        "/",
        follow_redirects=False,
    )

    assert home.status_code == 200

    app.dependency_overrides.clear()
