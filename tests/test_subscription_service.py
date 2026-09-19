from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app.database import Base
from bxk_app.db_models.subscription import (
    SubscriptionStatus,
    UserSubscription,
)
from bxk_app.db_models.user import User, UserRole
from bxk_app.services.subscription_service import (
    evaluate_subscription_access,
    set_manual_subscription_access,
)
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


def make_user(
    role=UserRole.BETA,
) -> User:
    return User(
        username=f"user-{role.value.lower()}",
        email=(
            f"user-{role.value.lower()}"
            "@example.com"
        ),
        password_hash=hash_app_password(
            "Password123!"
        ),
        role=role,
    )


def test_enforcement_disabled_preserves_beta_access():
    access = evaluate_subscription_access(
        make_user(),
        None,
        enforcement_enabled=False,
    )

    assert access["access_granted"] is True
    assert (
        access["access_reason"]
        == "ENFORCEMENT_DISABLED"
    )


def test_enforcement_denies_missing_subscription():
    access = evaluate_subscription_access(
        make_user(),
        None,
        enforcement_enabled=True,
    )

    assert access["access_granted"] is False
    assert (
        access["access_reason"]
        == "NO_SUBSCRIPTION"
    )


def test_active_subscription_grants_access():
    user = make_user()
    subscription = UserSubscription(
        user_id=user.id,
        status=SubscriptionStatus.ACTIVE,
    )

    access = evaluate_subscription_access(
        user,
        subscription,
        enforcement_enabled=True,
    )

    assert access["access_granted"] is True
    assert (
        access["access_reason"]
        == "ACTIVE_SUBSCRIPTION"
    )


def test_past_due_access_uses_grace_period():
    now = datetime.now(timezone.utc)
    user = make_user()
    subscription = UserSubscription(
        user_id=user.id,
        status=SubscriptionStatus.PAST_DUE,
        grace_period_ends_at=(
            now + timedelta(days=3)
        ),
    )

    access = evaluate_subscription_access(
        user,
        subscription,
        enforcement_enabled=True,
        now=now,
    )

    assert access["access_granted"] is True
    assert (
        access["access_reason"]
        == "PAYMENT_GRACE_PERIOD"
    )


def test_owner_always_bypasses_subscription():
    access = evaluate_subscription_access(
        make_user(UserRole.OWNER),
        None,
        enforcement_enabled=True,
    )

    assert access["access_granted"] is True
    assert access["access_reason"] == "OWNER_BYPASS"


def test_manual_access_can_be_granted_and_cleared(
    monkeypatch,
):
    factory = make_session_factory()

    monkeypatch.setattr(
        "bxk_app.config."
        "BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED",
        True,
    )

    with factory() as session:
        user = make_user()
        session.add(user)
        session.commit()
        user_id = str(user.id)

        granted = set_manual_subscription_access(
            session,
            user_id=user_id,
            granted=True,
        )

        assert granted["access_granted"] is True
        assert (
            granted["access_reason"]
            == "MANUAL_ACCESS"
        )

        cleared = set_manual_subscription_access(
            session,
            user_id=user_id,
            granted=None,
        )

        assert cleared["access_granted"] is False
        assert (
            cleared["access_reason"]
            == "SUBSCRIPTION_INACTIVE"
        )
