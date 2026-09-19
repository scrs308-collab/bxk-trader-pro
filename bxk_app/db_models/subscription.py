import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from bxk_app.database import Base


class SubscriptionStatus(str, enum.Enum):
    INCOMPLETE = "INCOMPLETE"
    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    PAUSED = "PAUSED"
    CANCELED = "CANCELED"
    UNPAID = "UNPAID"


class SubscriptionPlan(str, enum.Enum):
    PRO = "PRO"


class SubscriptionProvider(str, enum.Enum):
    MANUAL = "MANUAL"
    STRIPE = "STRIPE"


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    provider: Mapped[SubscriptionProvider] = (
        mapped_column(
            Enum(
                SubscriptionProvider,
                name="subscription_provider",
                native_enum=False,
            ),
            nullable=False,
            default=SubscriptionProvider.MANUAL,
        )
    )

    provider_customer_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )

    provider_subscription_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )

    provider_price_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    plan_code: Mapped[SubscriptionPlan] = (
        mapped_column(
            Enum(
                SubscriptionPlan,
                name="subscription_plan",
                native_enum=False,
            ),
            nullable=False,
            default=SubscriptionPlan.PRO,
        )
    )

    status: Mapped[SubscriptionStatus] = (
        mapped_column(
            Enum(
                SubscriptionStatus,
                name="subscription_status",
                native_enum=False,
            ),
            nullable=False,
            default=SubscriptionStatus.INCOMPLETE,
        )
    )

    current_period_end: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    trial_ends_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    grace_period_ends_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancel_at_period_end: Mapped[bool] = (
        mapped_column(
            Boolean,
            nullable=False,
            default=False,
            server_default="false",
        )
    )

    manual_access_granted: Mapped[
        bool | None
    ] = mapped_column(
        Boolean,
        nullable=True,
    )

    manual_access_expires_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BillingWebhookEvent(Base):
    __tablename__ = "billing_webhook_events"

    provider_event_id: Mapped[str] = (
        mapped_column(
            String(255),
            primary_key=True,
        )
    )

    event_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    payload_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    processed_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
