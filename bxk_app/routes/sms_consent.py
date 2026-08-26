from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)

from bxk_app.services.sms_consent_service import (
    record_sms_consent,
)


router = APIRouter(
    prefix="/api/sms",
    tags=["sms-consent"],
)


class SmsOptInRequest(BaseModel):
    phone_number: str = Field(
        min_length=8,
        max_length=40,
    )

    consent: bool


@router.post("/opt-in")
def sms_opt_in(
    payload: SmsOptInRequest,
):
    if payload.consent is not True:
        raise HTTPException(
            status_code=400,
            detail=(
                "Affirmative SMS consent "
                "is required."
            ),
        )

    try:
        result = record_sms_consent(
            payload.phone_number
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "status": "OPTED_IN",
        "message": (
            "BXK Trader Pro SMS consent "
            "was recorded."
        ),
        **result,
    }
