from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool
import pytest

from bxk_app.database import Base
from bxk_app.db_models.user import (
    UserRole,
)
from bxk_app.services.admin_user_service import (
    create_user,
    list_users,
)
from bxk_app.services.system_settings_service import (
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

    Base.metadata.create_all(
        engine
    )

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def test_create_beta_user():
    factory = make_session_factory()

    with factory() as session:
        result = create_user(
            session,
            username="beta1",
            email="beta1@example.com",
            role="BETA",
            temporary_password=(
                "Temporary123!"
            ),
        )

        assert result["username"] == "beta1"
        assert result["role"] == "BETA"
        assert result["is_active"] is True
        assert (
            result["must_change_password"]
            is True
        )

        assert "password_hash" not in result


def test_created_password_is_hashed():
    factory = make_session_factory()

    with factory() as session:
        result = create_user(
            session,
            username="beta1",
            email="beta1@example.com",
            role="BETA",
            temporary_password=(
                "Temporary123!"
            ),
        )

        from bxk_app.db_models.user import User

        user = session.get(
            User,
            __import__("uuid").UUID(
                result["id"]
            ),
        )

        assert (
            user.password_hash
            != "Temporary123!"
        )

        assert verify_app_password(
            "Temporary123!",
            user.password_hash,
        )


def test_owner_role_cannot_be_created():
    factory = make_session_factory()

    with factory() as session:
        with pytest.raises(
            ValueError
        ):
            create_user(
                session,
                username="owner2",
                email="owner2@example.com",
                role=UserRole.OWNER.value,
                temporary_password=(
                    "Temporary123!"
                ),
            )


def test_duplicate_username_is_case_insensitive():
    factory = make_session_factory()

    with factory() as session:
        create_user(
            session,
            username="BetaUser",
            email="one@example.com",
            role="BETA",
            temporary_password=(
                "Temporary123!"
            ),
        )

        with pytest.raises(
            ValueError,
            match="Username already exists",
        ):
            create_user(
                session,
                username="betauser",
                email="two@example.com",
                role="BETA",
                temporary_password=(
                    "Temporary123!"
                ),
            )


def test_duplicate_email_is_case_insensitive():
    factory = make_session_factory()

    with factory() as session:
        create_user(
            session,
            username="beta1",
            email="Beta@Example.com",
            role="BETA",
            temporary_password=(
                "Temporary123!"
            ),
        )

        with pytest.raises(
            ValueError,
            match="Email already exists",
        ):
            create_user(
                session,
                username="beta2",
                email="beta@example.com",
                role="VIEWER",
                temporary_password=(
                    "Temporary123!"
                ),
            )


def test_list_users_never_exposes_password_hash():
    factory = make_session_factory()

    with factory() as session:
        create_user(
            session,
            username="beta1",
            email="beta1@example.com",
            role="BETA",
            temporary_password=(
                "Temporary123!"
            ),
        )

        users = list_users(
            session
        )

        assert len(users) == 1
        assert (
            "password_hash"
            not in users[0]
        )
