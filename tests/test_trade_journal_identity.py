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
from bxk_app.db_models import (
    TradeJournal,
    User,
    UserRole,
)

import bxk_app.services.trade_journal_service as journal_service


def make_factory():
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


def add_user(
    factory,
    username,
    role,
):
    with factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash="unused",
            role=role,
            is_active=True,
            must_change_password=False,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        return user.id


def test_same_broker_order_id_isolated_per_user(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        journal_service,
        "database_configured",
        lambda: True,
    )

    first_id = add_user(
        factory,
        "journal_identity_one",
        UserRole.BETA,
    )

    second_id = add_user(
        factory,
        "journal_identity_two",
        UserRole.BETA,
    )

    first = (
        journal_service.
        record_submitted_trade(
            user_context={
                "user_id":
                    str(first_id),
                "role": "BETA",
            },
            broker_order_id=
                "SAME-ORDER-1",
            broker_status=
                "Received",
            session_factory=
                factory,
        )
    )

    second = (
        journal_service.
        record_submitted_trade(
            user_context={
                "user_id":
                    str(second_id),
                "role": "BETA",
            },
            broker_order_id=
                "SAME-ORDER-1",
            broker_status=
                "Received",
            session_factory=
                factory,
        )
    )

    assert first["recorded"] is True
    assert second["recorded"] is True

    assert (
        first["journal_id"]
        != second["journal_id"]
    )

    with factory() as session:
        rows = (
            session.execute(
                select(
                    TradeJournal
                ).where(
                    TradeJournal.
                    broker_order_id
                    == "SAME-ORDER-1"
                )
            )
            .scalars()
            .all()
        )

        assert len(rows) == 2

        assert {
            row.user_id
            for row in rows
        } == {
            first_id,
            second_id,
        }


def test_beta_does_not_adopt_legacy_row(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        journal_service,
        "database_configured",
        lambda: True,
    )

    beta_id = add_user(
        factory,
        "journal_identity_beta",
        UserRole.BETA,
    )

    with factory() as session:
        session.add(
            TradeJournal(
                user_id=None,
                broker_order_id=
                    "LEGACY-SAME",
                status="SUBMITTED",
            )
        )
        session.commit()

    result = (
        journal_service.
        record_submitted_trade(
            user_context={
                "user_id":
                    str(beta_id),
                "role": "BETA",
            },
            broker_order_id=
                "LEGACY-SAME",
            broker_status=
                "Received",
            session_factory=
                factory,
        )
    )

    assert result["created"] is True

    with factory() as session:
        rows = (
            session.execute(
                select(
                    TradeJournal
                ).where(
                    TradeJournal.
                    broker_order_id
                    == "LEGACY-SAME"
                )
            )
            .scalars()
            .all()
        )

        assert len(rows) == 2

        assert {
            row.user_id
            for row in rows
        } == {
            None,
            beta_id,
        }


def test_same_closing_order_id_allowed_per_user():
    factory = make_factory()

    first_id = add_user(
        factory,
        "journal_close_one",
        UserRole.BETA,
    )

    second_id = add_user(
        factory,
        "journal_close_two",
        UserRole.BETA,
    )

    with factory() as session:
        session.add_all([
            TradeJournal(
                user_id=first_id,
                broker_order_id=
                    "OPEN-ONE",
                closing_broker_order_id=
                    "CLOSE-SAME",
                status="CLOSED",
            ),
            TradeJournal(
                user_id=second_id,
                broker_order_id=
                    "OPEN-TWO",
                closing_broker_order_id=
                    "CLOSE-SAME",
                status="CLOSED",
            ),
        ])

        session.commit()

        rows = (
            session.execute(
                select(
                    TradeJournal
                ).where(
                    TradeJournal.
                    closing_broker_order_id
                    == "CLOSE-SAME"
                )
            )
            .scalars()
            .all()
        )

        assert len(rows) == 2
