from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    Text,
    func,
    true,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from bxk_app.database import Base


class SmsConsent(Base):
    __tablename__ = "sms_consents"

    phone_e164: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    consent_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    consent_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    consent_source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    consented_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[
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
