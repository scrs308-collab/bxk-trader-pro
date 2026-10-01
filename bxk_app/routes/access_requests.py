from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bxk_app.authorization import require_owner
from bxk_app.database import get_db
from bxk_app.db_models.access_request import AccessRequest
from bxk_app.services.email_service import (
    owner_notification_email,
    send_operational_email,
)


router = APIRouter(
    prefix="/api/access-requests",
    tags=["Access Requests"],
)


class AccessRequestStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class AccessRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=320)
    broker: str | None = Field(default=None, max_length=64)
    intended_use: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=200)

    @field_validator("full_name", "email", "broker", "intended_use", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
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
def submit_access_request(
    request_data: AccessRequestCreate,
    session: Session = Depends(get_db),
):
    # Hidden honeypot field. Bots commonly fill every input.
    if request_data.website:
        return {
            "accepted": True,
            "message": "Access request received.",
        }

    existing = session.execute(
        select(AccessRequest)
        .where(
            func.lower(AccessRequest.email)
            == request_data.email.lower()
        )
        .where(AccessRequest.status == "PENDING")
        .order_by(AccessRequest.created_at.desc())
    ).scalars().first()

    if existing is not None:
        return {
            "accepted": True,
            "message": (
                "An access request for this email is already pending review."
            ),
        }

    access_request = AccessRequest(
        full_name=request_data.full_name,
        email=request_data.email,
        broker=(request_data.broker or None),
        intended_use=(request_data.intended_use or None),
        status="PENDING",
    )

    session.add(access_request)
    session.commit()
    session.refresh(access_request)

    notification_email = (
        owner_notification_email()
    )

    if notification_email:
        try:
            send_operational_email(
                notification_email,
                subject=(
                    "New BXK Trader Pro "
                    "access request"
                ),
                text=(
                    "A new BXK Trader Pro access "
                    "request was submitted.\n\n"
                    f"Name: {access_request.full_name}\n"
                    f"Email: {access_request.email}\n"
                    f"Broker: {access_request.broker or 'Not provided'}\n"
                    f"Request ID: {access_request.id}\n\n"
                    "Review it in Trader Pro under "
                    "System > Access & Support Requests."
                ),
            )
        except Exception:
            # Request persistence must not fail
            # because an operational notification
            # provider is unavailable.
            pass

    return {
        "accepted": True,
        "request_id": str(access_request.id),
        "message": "Access request received.",
    }


@router.get("")
def list_access_requests(
    status: str | None = None,
    _owner: dict = Depends(require_owner),
    session: Session = Depends(get_db),
):
    query = select(AccessRequest).order_by(
        AccessRequest.created_at.desc()
    )

    if status:
        query = query.where(
            AccessRequest.status == status.upper()
        )

    requests = session.execute(
        query
    ).scalars().all()

    return {
        "requests": [
            {
                "id": str(item.id),
                "full_name": item.full_name,
                "email": item.email,
                "broker": item.broker,
                "intended_use": item.intended_use,
                "status": item.status,
                "created_at": (
                    item.created_at.isoformat()
                    if item.created_at
                    else None
                ),
            }
            for item in requests
        ]
    }



@router.patch("/{request_id}/status")
def update_access_request_status(
    request_id: str,
    request_data: AccessRequestStatusUpdate,
    _owner: dict = Depends(require_owner),
    session: Session = Depends(get_db),
):
    allowed = {
        "PENDING",
        "APPROVED",
        "DECLINED",
        "CLOSED",
    }

    status = str(
        request_data.status or ""
    ).strip().upper()

    if status not in allowed:
        raise HTTPException(
            status_code=422,
            detail="Unsupported access-request status.",
        )

    try:
        import uuid

        parsed_id = uuid.UUID(
            str(request_id)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="Access request not found.",
        ) from exc

    item = session.get(
        AccessRequest,
        parsed_id,
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Access request not found.",
        )

    item.status = status
    session.commit()
    session.refresh(item)

    if status in {
        "APPROVED",
        "DECLINED",
        "CLOSED",
    }:
        try:
            subject = (
                "BXK Trader Pro access request "
                + status.lower()
            )

            if status == "APPROVED":
                message = (
                    "Your BXK Trader Pro access "
                    "request has been approved. "
                    "Account credentials are issued "
                    "separately by BXK."
                )
            elif status == "DECLINED":
                message = (
                    "Your BXK Trader Pro access "
                    "request has been declined."
                )
            else:
                message = (
                    "Your BXK Trader Pro access "
                    "request has been closed."
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
