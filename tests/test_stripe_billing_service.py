from datetime import datetime, timezone
from types import SimpleNamespace
import hashlib
import hmac
import json
import time
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models.subscription import (
    BillingWebhookEvent,
    SubscriptionProvider,
    SubscriptionStatus,
    UserSubscription,
)
from bxk_app.db_models.user import User, UserRole
from bxk_app.services.stripe_billing_service import (
    BillingStateError,
    BillingWebhookConflictError,
    billing_configuration_status,
    construct_stripe_event,
    create_checkout_session,
    create_customer_portal_session,
    process_stripe_webhook,
)
from bxk_app.services.subscription_service import (
    evaluate_subscription_access,
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


def add_user(
    session: Session,
    *,
    username="beta-billing",
    role=UserRole.BETA,
):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_app_password(
            "Password123!"
        ),
        role=role,
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def billing_config(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_BILLING_ENABLED",
        True,
    )
    monkeypatch.setattr(
        config,
        "STRIPE_SECRET_KEY",
        "sk_test_bxk",
    )
    monkeypatch.setattr(
        config,
        "STRIPE_WEBHOOK_SECRET",
        "whsec_bxk",
    )
    monkeypatch.setattr(
        config,
        "STRIPE_PRICE_PRO_MONTHLY",
        "price_monthly",
    )
    monkeypatch.setattr(
        config,
        "STRIPE_PRICE_PRO_ANNUAL",
        "price_annual",
    )
    monkeypatch.setattr(
        config,
        "BXK_PUBLIC_APP_URL",
        "https://app.bxktraderpro.com",
    )
    monkeypatch.setattr(
        config,
        "BXK_STRIPE_PAST_DUE_GRACE_DAYS",
        3,
    )


class FakeCheckoutSessions:
    def __init__(self):
        self.params = None
        self.options = None

    def create(self, params, options=None):
        self.params = params
        self.options = options
        return SimpleNamespace(
            id="cs_test_bxk",
            url="https://checkout.stripe.test/bxk",
        )


class FakePortalSessions:
    def __init__(self):
        self.params = None

    def create(self, params, options=None):
        self.params = params
        return SimpleNamespace(
            url="https://billing.stripe.test/bxk",
        )


class FakeStripeClient:
    def __init__(self):
        self.checkout_sessions = FakeCheckoutSessions()
        self.portal_sessions = FakePortalSessions()
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(
                sessions=self.checkout_sessions
            ),
            billing_portal=SimpleNamespace(
                sessions=self.portal_sessions
            ),
        )


def stripe_event(
    event_id,
    event_type,
    obj,
    *,
    created=1_800_000_000,
):
    return {
        "id": event_id,
        "type": event_type,
        "created": created,
        "data": {"object": obj},
    }


def payload(event):
    return json.dumps(
        event,
        sort_keys=True,
    ).encode("utf-8")


def subscription_object(
    user,
    *,
    status="active",
    price_id="price_monthly",
    subscription_id="sub_bxk",
    customer_id="cus_bxk",
    period_end=1_803_000_000,
):
    return {
        "id": subscription_id,
        "customer": customer_id,
        "status": status,
        "cancel_at_period_end": False,
        "trial_end": None,
        "metadata": {
            "bxk_user_id": str(user.id),
            "provider_price_id": price_id,
        },
        "items": {
            "data": [
                {
                    "price": {"id": price_id},
                    "current_period_end": period_end,
                }
            ]
        },
    }


def test_billing_configuration_never_exposes_secrets(
    billing_config,
):
    status = billing_configuration_status()

    assert status["enabled"] is True
    assert status["checkout_configured"] is True
    assert status["webhook_configured"] is True
    assert status["plans"]["MONTHLY"][
        "available"
    ] is True
    assert "secret" not in json.dumps(
        status
    ).lower()
    assert "price_monthly" not in json.dumps(
        status
    )


def test_construct_event_verifies_stripe_signature(
    billing_config,
):
    event = stripe_event(
        "evt_signed",
        "invoice.paid",
        {"id": "in_signed"},
    )
    body = payload(event)
    timestamp = int(time.time())
    signed_payload = (
        f"{timestamp}.".encode("utf-8") + body
    )
    signature = hmac.new(
        b"whsec_bxk",
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    parsed = construct_stripe_event(
        body,
        f"t={timestamp},v1={signature}",
    )

    assert parsed["id"] == "evt_signed"


def test_construct_event_rejects_bad_signature(
    billing_config,
):
    event = stripe_event(
        "evt_bad_signature",
        "invoice.paid",
        {"id": "in_bad"},
    )

    with pytest.raises(
        ValueError,
        match="signature is invalid",
    ):
        construct_stripe_event(
            payload(event),
            "t=1,v1=not-valid",
        )


def test_checkout_uses_server_price_and_user_identity(
    billing_config,
):
    factory = make_session_factory()
    client = FakeStripeClient()

    with factory() as session:
        user = add_user(session)
        result = create_checkout_session(
            session,
            user=user,
            interval="MONTHLY",
            request_token=str(uuid.uuid4()),
            client=client,
        )

        params = client.checkout_sessions.params
        assert result["url"].startswith(
            "https://checkout.stripe.test/"
        )
        assert params["line_items"] == [
            {
                "price": "price_monthly",
                "quantity": 1,
            }
        ]
        assert params["client_reference_id"] == str(
            user.id
        )
        assert params["customer_email"] == user.email
        assert (
            params["subscription_data"]["metadata"]
            ["bxk_user_id"]
            == str(user.id)
        )
        assert (
            "idempotency_key"
            in client.checkout_sessions.options
        )


def test_checkout_rejects_owner(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        owner = add_user(
            session,
            username="owner-billing",
            role=UserRole.OWNER,
        )
        with pytest.raises(
            BillingStateError,
            match="permanent access",
        ):
            create_checkout_session(
                session,
                user=owner,
                interval="MONTHLY",
                request_token=str(uuid.uuid4()),
                client=FakeStripeClient(),
            )


def test_checkout_rejects_existing_active_stripe_plan(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        user = add_user(session)
        session.add(
            UserSubscription(
                user_id=user.id,
                provider=SubscriptionProvider.STRIPE,
                provider_customer_id="cus_existing",
                provider_subscription_id="sub_existing",
                provider_price_id="price_monthly",
                status=SubscriptionStatus.ACTIVE,
            )
        )
        session.commit()

        with pytest.raises(
            BillingStateError,
            match="already has an active",
        ):
            create_checkout_session(
                session,
                user=user,
                interval="ANNUAL",
                request_token=str(uuid.uuid4()),
                client=FakeStripeClient(),
            )


def test_portal_uses_saved_customer_only(
    billing_config,
):
    factory = make_session_factory()
    client = FakeStripeClient()

    with factory() as session:
        user = add_user(session)
        session.add(
            UserSubscription(
                user_id=user.id,
                provider=SubscriptionProvider.STRIPE,
                provider_customer_id="cus_saved",
                status=SubscriptionStatus.ACTIVE,
            )
        )
        session.commit()

        result = create_customer_portal_session(
            session,
            user=user,
            client=client,
        )

        assert result["url"].startswith(
            "https://billing.stripe.test/"
        )
        assert client.portal_sessions.params == {
            "customer": "cus_saved",
            "return_url": (
                "https://app.bxktraderpro.com/"
                "subscription"
            ),
        }


def test_checkout_then_subscription_event_grants_access(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        user = add_user(session)
        checkout = stripe_event(
            "evt_checkout",
            "checkout.session.completed",
            {
                "id": "cs_bxk",
                "client_reference_id": str(user.id),
                "customer": "cus_bxk",
                "subscription": "sub_bxk",
                "metadata": {
                    "provider_price_id": (
                        "price_monthly"
                    ),
                },
            },
        )
        checkout_result = process_stripe_webhook(
            session,
            event=checkout,
            payload=payload(checkout),
        )

        assert checkout_result["outcome"] == (
            "CHECKOUT_LINKED"
        )

        event = stripe_event(
            "evt_subscription",
            "customer.subscription.created",
            subscription_object(user),
            created=1_800_000_001,
        )
        result = process_stripe_webhook(
            session,
            event=event,
            payload=payload(event),
        )

        record = session.scalar(
            select(UserSubscription).where(
                UserSubscription.user_id
                == user.id
            )
        )
        access = evaluate_subscription_access(
            user,
            record,
            enforcement_enabled=True,
        )

        assert result["outcome"] == (
            "SUBSCRIPTION_SYNCHRONIZED"
        )
        assert record.status == (
            SubscriptionStatus.ACTIVE
        )
        assert record.provider_price_id == (
            "price_monthly"
        )
        assert access["access_granted"] is True


def test_duplicate_webhook_is_idempotent(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        user = add_user(session)
        event = stripe_event(
            "evt_duplicate",
            "customer.subscription.created",
            subscription_object(user),
        )
        body = payload(event)

        process_stripe_webhook(
            session,
            event=event,
            payload=body,
        )
        duplicate = process_stripe_webhook(
            session,
            event=event,
            payload=body,
        )

        assert duplicate == {
            "processed": False,
            "duplicate": True,
            "outcome": "DUPLICATE_EVENT",
        }
        events = session.scalars(
            select(BillingWebhookEvent)
        ).all()
        assert len(events) == 1


def test_reused_event_id_with_changed_payload_fails(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        user = add_user(session)
        event = stripe_event(
            "evt_conflict",
            "customer.subscription.created",
            subscription_object(user),
        )
        process_stripe_webhook(
            session,
            event=event,
            payload=payload(event),
        )

        with pytest.raises(
            BillingWebhookConflictError,
            match="different payload",
        ):
            process_stripe_webhook(
                session,
                event=event,
                payload=b"changed",
            )


def test_stale_subscription_event_cannot_revoke_access(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        user = add_user(session)
        active = stripe_event(
            "evt_active",
            "customer.subscription.updated",
            subscription_object(user),
            created=1_800_000_200,
        )
        process_stripe_webhook(
            session,
            event=active,
            payload=payload(active),
        )

        stale = stripe_event(
            "evt_stale",
            "customer.subscription.deleted",
            subscription_object(
                user,
                status="canceled",
            ),
            created=1_800_000_100,
        )
        result = process_stripe_webhook(
            session,
            event=stale,
            payload=payload(stale),
        )

        record = session.scalar(
            select(UserSubscription).where(
                UserSubscription.user_id
                == user.id
            )
        )
        assert result["outcome"] == (
            "IGNORED_STALE_EVENT"
        )
        assert record.status == (
            SubscriptionStatus.ACTIVE
        )


def test_unknown_stripe_price_never_grants_access(
    billing_config,
):
    user = User(
        username="bad-price",
        email="bad-price@example.com",
        password_hash="not-used",
        role=UserRole.BETA,
    )
    subscription = UserSubscription(
        user_id=uuid.uuid4(),
        provider=SubscriptionProvider.STRIPE,
        provider_price_id="price_attacker",
        status=SubscriptionStatus.ACTIVE,
    )

    access = evaluate_subscription_access(
        user,
        subscription,
        enforcement_enabled=True,
    )

    assert access["access_granted"] is False
    assert access["access_reason"] == (
        "UNRECOGNIZED_PRICE"
    )


def test_payment_failure_starts_grace_period(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        user = add_user(session)
        record = UserSubscription(
            user_id=user.id,
            provider=SubscriptionProvider.STRIPE,
            provider_customer_id="cus_bxk",
            provider_subscription_id="sub_bxk",
            provider_price_id="price_monthly",
            status=SubscriptionStatus.ACTIVE,
        )
        session.add(record)
        session.commit()

        event = stripe_event(
            "evt_failed",
            "invoice.payment_failed",
            {
                "id": "in_failed",
                "subscription": "sub_bxk",
            },
        )
        result = process_stripe_webhook(
            session,
            event=event,
            payload=payload(event),
        )

        assert result["outcome"] == (
            "PAYMENT_FAILURE_RECORDED"
        )
        assert record.status == (
            SubscriptionStatus.PAST_DUE
        )
        assert record.grace_period_ends_at is not None
        assert (
            record.grace_period_ends_at.replace(
                tzinfo=timezone.utc
            )
            > datetime.now(timezone.utc)
        )


def test_stripe_identifier_cannot_move_between_users(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        first = add_user(
            session,
            username="first-billing",
        )
        second = add_user(
            session,
            username="second-billing",
        )
        session.add(
            UserSubscription(
                user_id=first.id,
                provider=SubscriptionProvider.STRIPE,
                provider_customer_id="cus_taken",
                provider_subscription_id="sub_taken",
                provider_price_id="price_monthly",
                status=SubscriptionStatus.ACTIVE,
            )
        )
        session.commit()

        event = stripe_event(
            "evt_hijack",
            "customer.subscription.updated",
            subscription_object(
                second,
                customer_id="cus_taken",
                subscription_id="sub_taken",
            ),
        )

        with pytest.raises(
            BillingWebhookConflictError,
            match="another BXK account",
        ):
            process_stripe_webhook(
                session,
                event=event,
                payload=payload(event),
            )


def test_current_period_end_uses_subscription_item(
    billing_config,
):
    factory = make_session_factory()

    with factory() as session:
        user = add_user(session)
        event = stripe_event(
            "evt_period",
            "customer.subscription.created",
            subscription_object(
                user,
                period_end=1_900_000_000,
            ),
        )
        process_stripe_webhook(
            session,
            event=event,
            payload=payload(event),
        )

        record = session.scalar(
            select(UserSubscription).where(
                UserSubscription.user_id
                == user.id
            )
        )
        assert int(
            record.current_period_end.replace(
                tzinfo=timezone.utc
            ).timestamp()
        ) == 1_900_000_000
