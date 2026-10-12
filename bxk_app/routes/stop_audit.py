from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy.orm import Session

from bxk_app.authorization import require_owner_or_beta
from bxk_app.database import get_db
from bxk_app.services.broker_connection_service import BrokerConnectionInvalid, BrokerConnectionRequired, resolve_broker
from bxk_app.services.stop_audit_service import enroll_stop_audit, get_stop_audits

router = APIRouter(prefix="/api/stop-audit", tags=["stop-audit"])


class EnrollmentRequest(BaseModel):
    journal_id: str = Field(min_length=36, max_length=36)
    confirm_stop_out: StrictBool
    entry_costs: float = Field(ge=0, le=1_000_000, allow_inf_nan=False, strict=True)
    actual_exit_costs: float = Field(ge=0, le=1_000_000, allow_inf_nan=False, strict=True)
    hypothetical_exit_costs: float = Field(ge=0, le=1_000_000, allow_inf_nan=False, strict=True)


@router.get("")
def stop_audit_list(user_context: dict = Depends(require_owner_or_beta)):
    try:
        return get_stop_audits(user_context=user_context)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("")
def stop_audit_enroll(payload: EnrollmentRequest, user_context: dict = Depends(require_owner_or_beta), session: Session = Depends(get_db)):
    try:
        broker_client = resolve_broker(session, user_context=user_context, broker_name="tastytrade")
        return enroll_stop_audit(**payload.model_dump(), user_context=user_context, broker_client=broker_client)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except (ValueError, BrokerConnectionInvalid, BrokerConnectionRequired) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
