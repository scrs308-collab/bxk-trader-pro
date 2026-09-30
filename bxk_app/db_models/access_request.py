import uuid

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from bxk_app.database import Base


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    full_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )

    broker: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    intended_use: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
        index=True,
    )

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
