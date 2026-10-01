from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from bxk_app.authorization import require_owner
from bxk_app.database import get_db
from bxk_app.db_models.support_request import SupportRequest
from bxk_app.services.email_service import (
    owner_notification_email,
    send_operational_email,
)


router = APIRouter(
    prefix="/api/support-requests",
    tags=["Support Requests"],
)


class SupportRequestStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class SupportRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=320)
    subject: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=5, max_length=4000)
    website: str | None = Field(default=None, max_length=200)

    @field_validator("name", "email", "subject", "message", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str):
        if (
            "@" not in value
            or "." not in value.rsplit("@", 1)[-1]
            or any(char.isspace() for char in value)
        ):
            raise ValueError("Enter a valid email address.")
        return value.lower()


@router.post("", status_code=202)
def create_support_request(
    request_data: SupportRequestCreate,
    session: Session = Depends(get_db),
):
    if request_data.website:
        return {
            "accepted": True,
            "message": "Support request received.",
        }

    item = SupportRequest(
        name=request_data.name,
        email=request_data.email,
        subject=request_data.subject,
        message=request_data.message,
        status="OPEN",
    )

    session.add(item)
    session.commit()
    session.refresh(item)

    notification_email = (
        owner_notification_email()
    )

    if notification_email:
        try:
            send_operational_email(
                notification_email,
                subject=(
                    "New BXK Trader Pro "
                    "support request"
                ),
                text=(
                    "A new BXK Trader Pro support "
                    "request was submitted.\n\n"
                    f"Name: {item.name}\n"
                    f"Email: {item.email}\n"
                    f"Subject: {item.subject}\n"
                    f"Request ID: {item.id}\n\n"
                    "Review it in Trader Pro under "
                    "System > Access & Support Requests."
                ),
            )
        except Exception:
            # Support persistence must not fail
            # because email notification delivery
            # is temporarily unavailable.
            pass

    try:
        send_operational_email(
            item.email,
            subject=(
                "BXK Trader Pro support request received"
            ),
            text=(
                "We received your BXK Trader Pro "
                "support request.\n\n"
                f"Subject: {item.subject}\n"
                f"Request ID: {item.id}\n\n"
                "A BXK administrator can review the "
                "request from the Trader Pro System tab."
            ),
        )
    except Exception:
        pass

    return {
        "accepted": True,
        "request_id": str(item.id),
        "message": "Support request received.",
    }


@router.get("")
def list_support_requests(
    _owner: dict = Depends(require_owner),
    session: Session = Depends(get_db),
):
    items = session.execute(
        select(SupportRequest)
        .order_by(SupportRequest.created_at.desc())
    ).scalars().all()

    return {
        "requests": [
            {
                "id": str(item.id),
                "name": item.name,
                "email": item.email,
                "subject": item.subject,
                "message": item.message,
                "status": item.status,
                "created_at": (
                    item.created_at.isoformat()
                    if item.created_at
                    else None
                ),
            }
            for item in items
        ]
    }



@router.patch("/{request_id}/status")
def update_support_request_status(
    request_id: str,
    request_data: SupportRequestStatusUpdate,
    _owner: dict = Depends(require_owner),
    session: Session = Depends(get_db),
):
    allowed = {
        "OPEN",
        "RESOLVED",
        "CLOSED",
    }

    status = str(
        request_data.status or ""
    ).strip().upper()

    if status not in allowed:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail="Unsupported support-request status.",
        )

    try:
        import uuid

        parsed_id = uuid.UUID(
            str(request_id)
        )
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Support request not found.",
        ) from exc

    item = session.get(
        SupportRequest,
        parsed_id,
    )

    if item is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Support request not found.",
        )

    item.status = status
    session.commit()
    session.refresh(item)

    if status in {
        "RESOLVED",
        "CLOSED",
    }:
        try:
            subject = (
                "BXK Trader Pro support request "
                + status.lower()
            )

            message = (
                "Your BXK Trader Pro support "
                f"request has been {status.lower()}."
            )

            send_operational_email(
                item.email,
                subject=subject,
                text=message,
            )
        except Exception:
            pass

    return {
        "id": str(item.id),
        "status": item.status,
    }
