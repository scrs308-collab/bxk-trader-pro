import uuid

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from bxk_app.database import Base
from bxk_app.db_models.execution_audit import (
    ExecutionAudit,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.services.system_settings_service import (
    hash_app_password,
)
from bxk_app.services.user_execution_audit_service import (
    write_user_order_audit,
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


def add_beta_user(
    factory,
):
    with factory() as session:
        user = User(
            username="audit_beta",
            email="audit_beta@example.com",
            password_hash=(
                hash_app_password(
                    "Password123!"
                )
            ),
            role=UserRole.BETA,
            is_active=True,
            must_change_password=False,
        )

        session.add(
            user
        )

        session.commit()
        session.refresh(
            user
        )

        return str(
            user.id
        )


def test_user_execution_audit_is_user_scoped():
    factory = make_session_factory()

    user_id = add_beta_user(
        factory
    )

    with factory() as session:
        result = write_user_order_audit(
            session,
            user_context={
                "user_id":
                    user_id,
                "role":
                    "BETA",
            },
            event=
                "SUBMISSION_ATTEMPT",
            status="PENDING",
            review_id=
                "review-token-123456789",
            account=
                "BETA12345678",
            order={
                "strategy":
                    "SPX Iron Condor",
                "symbol":
                    "SPX",
                "quantity":
                    1,
                "secret_field":
                    "must-not-persist",
            },
        )

        assert (
            result["user_id"]
            == user_id
        )

        audit = session.scalar(
            select(
                ExecutionAudit
            )
        )

        assert audit is not None

        assert str(
            audit.user_id
        ) == user_id

        assert (
            audit.account_masked
            == "***5678"
        )

        assert (
            audit.review_reference
            == "review-token"
        )

        assert (
            audit.order_snapshot[
                "strategy"
            ]
            == "SPX Iron Condor"
        )

        assert (
            "secret_field"
            not in audit.order_snapshot
        )


def test_user_execution_audit_requires_database_user():
    factory = make_session_factory()

    with factory() as session:
        try:
            write_user_order_audit(
                session,
                user_context={
                    "user_id": None,
                    "role": "BETA",
                },
                event=
                    "SUBMISSION_ATTEMPT",
            )

        except ValueError as exc:
            assert (
                "Database-backed user ID"
                in str(exc)
            )

        else:
            raise AssertionError(
                "Missing user ID must fail closed."
            )


def test_user_execution_audits_do_not_collide_between_users():
    factory = make_session_factory()

    first_id = add_beta_user(
        factory
    )

    with factory() as session:
        second = User(
            username="audit_beta_2",
            email="audit_beta_2@example.com",
            password_hash=(
                hash_app_password(
                    "Password123!"
                )
            ),
            role=UserRole.BETA,
            is_active=True,
            must_change_password=False,
        )

        session.add(
            second
        )

        session.commit()
        session.refresh(
            second
        )

        second_id = str(
            second.id
        )

    with factory() as session:
        for user_id in (
            first_id,
            second_id,
        ):
            write_user_order_audit(
                session,
                user_context={
                    "user_id":
                        user_id,
                    "role":
                        "BETA",
                },
                event="SUBMITTED",
                status="SUBMITTED",
                order_id="ORDER-1",
            )

        rows = session.scalars(
            select(
                ExecutionAudit
            )
        ).all()

        assert len(rows) == 2

        assert {
            str(row.user_id)
            for row in rows
        } == {
            first_id,
            second_id,
        }
