from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bxk_app.authorization import require_owner
from bxk_app.database import get_db
from bxk_app.db_models.access_request import AccessRequest


router = APIRouter(
    prefix="/api/access-requests",
    tags=["Access Requests"],
)


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
