import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from bxk_app.database import Base


class BrokerAccount(Base):
    """
    One account authorized through a broker connection.

    A single broker connection may expose multiple accounts.
    """

    __tablename__ = "broker_accounts"

    __table_args__ = (
        UniqueConstraint(
            "broker_connection_id",
            "account_number",
            name=(
                "uq_broker_accounts_"
                "connection_account"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    broker_connection_id: Mapped[uuid.UUID] = (
        mapped_column(
            Uuid(as_uuid=True),
            ForeignKey(
                "broker_connections.id",
                ondelete="CASCADE",
            ),
            nullable=False,
            index=True,
        )
    )

    account_number: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    broker_account_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    nickname: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    account_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
