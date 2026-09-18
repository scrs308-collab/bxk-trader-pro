from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)

from bxk_app.services.sms_consent_service import (
    get_user_sms_subscription,
    record_user_sms_consent,
    revoke_user_sms_consent,
)
from bxk_app.authorization import require_owner_or_beta


router = APIRouter(
    prefix="/api/sms",
    tags=["sms-consent"],
)


class SmsOptInRequest(BaseModel):
    phone_number: str | None = Field(
        default=None,
        min_length=8,
        max_length=40,
    )

    consent: bool


@router.post("/opt-in")
def sms_opt_in(
    payload: SmsOptInRequest,
    user_context: dict = Depends(
        require_owner_or_beta
    ),
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
        user_id = user_context.get("user_id")

        if not user_id:
            raise ValueError(
                "A database-backed account is required."
            )

        result = record_user_sms_consent(
            user_id=user_id,
            phone_number=payload.phone_number,
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


@router.get("/subscription")
def sms_subscription(
    user_context: dict = Depends(
        require_owner_or_beta
    ),
):
    try:
        return get_user_sms_subscription(
            user_context.get("user_id")
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post("/opt-out")
def sms_opt_out(
    user_context: dict = Depends(
        require_owner_or_beta
    ),
):
    try:
        result = revoke_user_sms_consent(
            user_context.get("user_id")
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return {
        "status": "OPTED_OUT",
        **result,
    }
