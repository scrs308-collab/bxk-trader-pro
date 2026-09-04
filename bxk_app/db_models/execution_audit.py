import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from bxk_app.database import Base


class ExecutionAudit(Base):
    __tablename__ = "execution_audits"

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
        nullable=False,
        index=True,
    )

    broker: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="tastytrade",
        index=True,
    )

    event: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    reason_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    review_reference: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    account_masked: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    order_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    broker_status: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    order_snapshot: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
