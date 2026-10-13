"""Explicit owner invitations and public single-use password setup."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from bxk_app.authorization import require_owner
from bxk_app.database import get_db
from bxk_app.services.admin_user_service import serialize_user
from bxk_app.db_models.user import User
from bxk_app.services.setup_invitation_service import (
    InvitationCooldown, InvalidSetupLink, issue_setup_invitation,
    public_app_origin, redeem_setup_invitation,
)
import uuid

router = APIRouter(tags=["Account Setup"])
SECURE_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


class SetupInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_email: str
    expected_username: str


class PasswordSetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr
    new_password: SecretStr


def _check_origin(request: Request):
    # Invitation creation uses an owner cookie; require an explicit same-origin
    # browser request instead of relying solely on SameSite cookie behavior.
    try:
        expected = public_app_origin()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Account setup is not configured.") from exc
    if request.headers.get("origin") != expected:
        raise HTTPException(status_code=403, detail="A same-origin account setup request is required.")


@router.post("/api/admin/users/{user_id}/setup-invitation")
def send_setup_invitation(user_id: str, payload: SetupInviteRequest, request: Request,
                          owner: dict = Depends(require_owner), session: Session = Depends(get_db)):
    _check_origin(request)
    try:
        result = issue_setup_invitation(session, user_id=user_id,
            expected_email=payload.expected_email, expected_username=payload.expected_username,
            owner_id=owner.get("user_id"))
        user = session.get(User, uuid.UUID(user_id), populate_existing=True)
        return JSONResponse({"invitation": result, "user": serialize_user(user, session=session)}, headers=SECURE_HEADERS)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvitationCooldown as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "60"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError:
        session.rollback()
        # It may have failed after a provider accepted the message. Never
        # encourage blind retries or expose SQL parameters / bearer material.
        return JSONResponse(status_code=503, content={"detail": "Invitation status is unconfirmed. Refresh the account and check the recipient's inbox before trying again."}, headers=SECURE_HEADERS)


@router.post("/api/auth/setup-password")
def setup_password(payload: PasswordSetupRequest, request: Request, session: Session = Depends(get_db)):
    _check_origin(request)
    try:
        result = redeem_setup_invitation(session, token=payload.token.get_secret_value(),
                                          new_password=payload.new_password.get_secret_value())
        return JSONResponse(result, headers=SECURE_HEADERS)
    except InvalidSetupLink as exc:
        session.rollback()
        return JSONResponse(status_code=400, content={"detail": str(exc), "code": "INVALID_SETUP_LINK"}, headers=SECURE_HEADERS)
    except ValueError as exc:
        session.rollback()
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "INVALID_PASSWORD"}, headers=SECURE_HEADERS)
    except SQLAlchemyError:
        session.rollback()
        return JSONResponse(status_code=503, content={"detail": "Password setup is temporarily unavailable. Please try again."}, headers=SECURE_HEADERS)
