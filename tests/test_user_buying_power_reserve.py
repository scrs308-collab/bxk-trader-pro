from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from bxk_app.database import Base
from bxk_app.db_models.user import User, UserRole
from bxk_app.routes import order as order_route
from bxk_app.routes.buying_power_settings import (
    ReserveUpdate,
    get_reserve,
    update_reserve,
)


def test_beta_reserve_is_saved_and_used_by_order_preflight(monkeypatch):
    monkeypatch.setattr(order_route, "BXK_MIN_REMAINING_BUYING_POWER", 5000.0)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        beta = User(
            username="katiedixon530",
            email="katie@example.com",
            password_hash="test-hash",
            role=UserRole.BETA,
        )
        owner = User(
            username="bxkcapital",
            email="owner@example.com",
            password_hash="test-hash",
            role=UserRole.OWNER,
        )
        session.add_all([beta, owner])
        session.commit()

        beta_context = {"user_id": str(beta.id), "role": "BETA"}
        owner_context = {"user_id": str(owner.id), "role": "OWNER"}
        saved = update_reserve(
            ReserveUpdate(min_remaining_buying_power=Decimal("1000.00")),
            beta_context,
            session,
        )

        assert saved == {
            "min_remaining_buying_power": 1000.0,
            "user_override": True,
        }
        assert get_reserve(beta_context, session) == saved
        assert order_route._user_buying_power_reserve(session, beta_context) == 1000.0
        assert order_route._user_buying_power_reserve(session, owner_context) == 5000.0

    engine.dispose()
