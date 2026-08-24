from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.services import user_service


def make_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    return Session(engine)


def configure_owner(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_APP_USERNAME",
        "joe",
    )

    monkeypatch.setattr(
        config,
        "BXK_APP_PASSWORD_HASH",
        "existing-password-hash",
    )

    monkeypatch.setenv(
        "BXK_APP_EMAIL",
        "joe@example.com",
    )


def test_bootstrap_creates_owner(
    monkeypatch,
):
    configure_owner(monkeypatch)

    with make_session() as session:
        result = (
            user_service.bootstrap_owner_user(
                session
            )
        )

        assert result["configured"] is True
        assert result["created"] is True
        assert result["existing"] is False
        assert result["user_id"]

        users = session.query(User).all()

        assert len(users) == 1

        owner = users[0]

        assert owner.username == "joe"
        assert owner.email == "joe@example.com"
        assert (
            owner.password_hash
            == "existing-password-hash"
        )
        assert owner.role == UserRole.OWNER
        assert owner.is_active is True
        assert (
            owner.must_change_password
            is False
        )


def test_bootstrap_is_idempotent(
    monkeypatch,
):
    configure_owner(monkeypatch)

    with make_session() as session:
        first = (
            user_service.bootstrap_owner_user(
                session
            )
        )

        second = (
            user_service.bootstrap_owner_user(
                session
            )
        )

        assert first["created"] is True
        assert second["created"] is False
        assert second["existing"] is True
        assert (
            first["user_id"]
            == second["user_id"]
        )

        assert session.query(User).count() == 1


def test_bootstrap_requires_configuration(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_APP_USERNAME",
        "",
    )

    monkeypatch.setattr(
        config,
        "BXK_APP_PASSWORD_HASH",
        "",
    )

    monkeypatch.delenv(
        "BXK_APP_EMAIL",
        raising=False,
    )

    with make_session() as session:
        result = (
            user_service.bootstrap_owner_user(
                session
            )
        )

        assert result == {
            "configured": False,
            "created": False,
            "existing": False,
            "user_id": None,
        }

        assert session.query(User).count() == 0


def test_bootstrap_rejects_email_conflict(
    monkeypatch,
):
    configure_owner(monkeypatch)

    with make_session() as session:
        session.add(
            User(
                username="someone_else",
                email="joe@example.com",
                password_hash="another-hash",
                role=UserRole.BETA,
            )
        )
        session.commit()

        try:
            user_service.bootstrap_owner_user(
                session
            )
        except RuntimeError as exc:
            assert (
                "email already belongs"
                in str(exc)
            )
        else:
            raise AssertionError(
                "Expected OWNER email conflict."
            )
