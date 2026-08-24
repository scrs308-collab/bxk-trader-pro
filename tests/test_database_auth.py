from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bxk_app.database import Base
from bxk_app.db_models.user import User, UserRole
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import (
    hash_app_password,
)


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def add_user(
    session_factory,
    *,
    username="beta1",
    password="StrongPassword123!",
    active=True,
):
    with session_factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_app_password(
                password
            ),
            role=UserRole.BETA,
            is_active=active,
        )

        session.add(user)
        session.commit()


def configure_database(
    monkeypatch,
    session_factory,
):
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


def test_database_credentials_authenticate(
    monkeypatch,
):
    session_factory = make_session_factory()

    add_user(session_factory)

    configure_database(
        monkeypatch,
        session_factory,
    )

    result = (
        auth_service
        .authenticate_database_credentials(
            "beta1",
            "StrongPassword123!",
        )
    )

    assert result["authenticated"] is True
    assert result["database_available"] is True
    assert result["reason"] == "AUTHENTICATED"
    assert result["user_id"]
    assert result["username"] == "beta1"
    assert result["role"] == "BETA"


def test_database_username_is_case_insensitive(
    monkeypatch,
):
    session_factory = make_session_factory()

    add_user(session_factory)

    configure_database(
        monkeypatch,
        session_factory,
    )

    result = (
        auth_service
        .authenticate_database_credentials(
            "BETA1",
            "StrongPassword123!",
        )
    )

    assert result["authenticated"] is True
    assert result["username"] == "beta1"


def test_database_wrong_password_rejected(
    monkeypatch,
):
    session_factory = make_session_factory()

    add_user(session_factory)

    configure_database(
        monkeypatch,
        session_factory,
    )

    result = (
        auth_service
        .authenticate_database_credentials(
            "beta1",
            "wrong-password",
        )
    )

    assert result["authenticated"] is False
    assert result["reason"] == "INVALID_PASSWORD"


def test_database_inactive_user_rejected(
    monkeypatch,
):
    session_factory = make_session_factory()

    add_user(
        session_factory,
        active=False,
    )

    configure_database(
        monkeypatch,
        session_factory,
    )

    result = (
        auth_service
        .authenticate_database_credentials(
            "beta1",
            "StrongPassword123!",
        )
    )

    assert result["authenticated"] is False
    assert result["reason"] == "USER_INACTIVE"


def test_database_auth_not_configured(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_service,
        "database_configured",
        lambda: False,
    )

    result = (
        auth_service
        .authenticate_database_credentials(
            "beta1",
            "anything",
        )
    )

    assert result["authenticated"] is False
    assert result["database_available"] is False
    assert (
        result["reason"]
        == "DATABASE_NOT_CONFIGURED"
    )
