from sqlalchemy import (
    DateTime,
    String,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from bxk_app.database import Base


class OvernightAlertState(Base):
    __tablename__ = "overnight_alert_states"

    scope: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    reason_code: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    last_alerted_state: Mapped[
        str | None
    ] = mapped_column(
        String(32),
        nullable=True,
    )

    last_alerted_at: Mapped[
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
