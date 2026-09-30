from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from bxk_app.authorization import require_owner
from bxk_app.database import get_db
from bxk_app.db_models.support_request import SupportRequest


router = APIRouter(
    prefix="/api/support-requests",
    tags=["Support Requests"],
)


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
