import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from bxk_app.database import (
    Base,
    normalize_database_url,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)


def test_normalize_postgresql_database_url():
    assert (
        normalize_database_url(
            "postgresql://user:pass@host/db"
        )
        == (
            "postgresql+psycopg://"
            "user:pass@host/db"
        )
    )


def test_normalize_railway_postgres_url():
    assert (
        normalize_database_url(
            "postgres://user:pass@host/db"
        )
        == (
            "postgresql+psycopg://"
            "user:pass@host/db"
        )
    )


def test_user_model_round_trip():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    user = User(
        username="beta_test",
        email="beta@example.com",
        password_hash="test-hash",
        role=UserRole.BETA,
    )

    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)

        assert isinstance(user.id, uuid.UUID)
        assert user.username == "beta_test"
        assert user.email == "beta@example.com"
        assert user.role == UserRole.BETA
        assert user.is_active is True
        assert user.must_change_password is False
        assert user.created_at is not None
        assert user.updated_at is not None

