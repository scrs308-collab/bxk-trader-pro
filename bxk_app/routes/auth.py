import logging
import os
import threading
import time

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, ConfigDict

from bxk_app import config
from bxk_app.services.auth_service import (
    SESSION_COOKIE_NAME,
    auth_configuration_status,
    clear_temporary_password,
    create_session_token,
    issue_temporary_password,
    verify_credentials,
    verify_session_token,
)

from bxk_app.services.email_service import (
    send_temporary_password_email,
)


logger = logging.getLogger(__name__)

_PASSWORD_RESET_LOCK = threading.Lock()
_PASSWORD_RESET_LAST_REQUEST = {}
_PASSWORD_RESET_COOLDOWN_SECONDS = 60


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    identity: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    username: str
    password: str


@router.post("/forgot-password")
def forgot_password(
    request_data: ForgotPasswordRequest,
):
    generic_response = {
        "accepted": True,
        "message": (
            "If the account information matches "
            "a BXK account, a temporary password "
            "will be emailed."
        ),
    }

    identity = str(
        request_data.identity or ""
    ).strip()

    if not identity:
        return generic_response

    cooldown_key = identity.casefold()
    now = time.monotonic()

    with _PASSWORD_RESET_LOCK:
        last_request = (
            _PASSWORD_RESET_LAST_REQUEST.get(
                cooldown_key
            )
        )

        if (
            last_request is not None
            and now - last_request
            < _PASSWORD_RESET_COOLDOWN_SECONDS
        ):
            return generic_response

        _PASSWORD_RESET_LAST_REQUEST[
            cooldown_key
        ] = now

    configured_username = str(
        config.BXK_APP_USERNAME or ""
    ).strip()

    configured_email = str(
        os.getenv("BXK_APP_EMAIL", "")
    ).strip()

    if (
        not configured_username
        or not configured_email
    ):
        return generic_response

    identity_matches = (
        identity.casefold()
        == configured_username.casefold()
        or identity.casefold()
        == configured_email.casefold()
    )

    if not identity_matches:
        return generic_response

    temporary_password = (
        issue_temporary_password(
            configured_username,
            ttl_seconds=900,
        )
    )

    if not temporary_password:
        return generic_response

    try:
        send_temporary_password_email(
            configured_email,
            temporary_password,
            expires_minutes=15,
        )
    except Exception:
        clear_temporary_password()

        logger.exception(
            "BXK password reset email failed."
        )

    return generic_response


@router.get("/status")
def auth_status(request: Request):
    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    session = (
        verify_session_token(token)
        if token
        else None
    )

    configuration = (
        auth_configuration_status()
    )

    return {
        **configuration,
        "authenticated": bool(session),
        "username": (
            session["username"]
            if session
            else None
        ),
    }


@router.post("/login")
def login(
    credentials: LoginRequest,
    response: Response,
):
    configuration = (
        auth_configuration_status()
    )

    if not configuration["configured"]:
        raise HTTPException(
            status_code=503,
            detail=(
                "BXK authentication is not "
                "fully configured."
            ),
        )

    if not verify_credentials(
        credentials.username,
        credentials.password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    token = create_session_token(
        credentials.username
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(
            config.BXK_SESSION_TTL_SECONDS
        ),
        httponly=True,
        secure=bool(
            config.BXK_AUTH_COOKIE_SECURE
        ),
        samesite="strict",
        path="/",
    )

    return {
        "authenticated": True,
        "username": credentials.username,
        "auth_enabled": bool(
            config.BXK_AUTH_ENABLED
        ),
        "message": (
            "BXK authentication successful."
        ),
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=bool(
            config.BXK_AUTH_COOKIE_SECURE
        ),
        samesite="strict",
    )

    return {
        "authenticated": False,
        "message": "BXK session ended.",
    }
