import logging
import os
import threading
import time

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.database import get_db
from bxk_app.services.auth_service import (
    SESSION_COOKIE_NAME,
    auth_configuration_status,
    authenticate_credentials,
    clear_temporary_password,
    create_database_session_token,
    create_session_token,
    issue_temporary_password,
    verify_credentials,
    verify_session_token,
)

from bxk_app.services.email_service import (
    send_temporary_password_email,
)

from bxk_app.services.user_service import (
    change_user_password,
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


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    current_password: str
    new_password: str


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
        "user_id": (
            session.get("user_id")
            if session
            else None
        ),
        "username": (
            session["username"]
            if session
            else None
        ),
        "role": (
            session.get("role")
            if session
            else None
        ),
        "must_change_password": (
            session.get(
                "must_change_password",
                False,
            )
            if session
            else False
        ),
        "auth_source": (
            session.get("auth_source")
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

    authentication = authenticate_credentials(
        credentials.username,
        credentials.password,
    )

    if not authentication["authenticated"]:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    if (
        authentication["auth_source"]
        == "DATABASE"
    ):
        token = create_database_session_token(
            authentication["user_id"]
        )
    else:
        token = create_session_token(
            authentication["username"]
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
        "user_id": authentication["user_id"],
        "username": authentication["username"],
        "role": authentication["role"],
        "must_change_password":
            authentication[
                "must_change_password"
            ],
        "auth_source":
            authentication["auth_source"],
        "auth_enabled": bool(
            config.BXK_AUTH_ENABLED
        ),
        "message": (
            "BXK authentication successful."
        ),
    }




@router.post("/change-password")
def change_password(
    request_data: ChangePasswordRequest,
    request: Request,
    session: Session = Depends(
        get_db
    ),
):
    authenticated_user = getattr(
        request.state,
        "bxk_user",
        None,
    )

    if not isinstance(
        authenticated_user,
        dict,
    ):
        raise HTTPException(
            status_code=401,
            detail="BXK authentication required.",
        )

    if (
        authenticated_user.get("auth_source")
        != "DATABASE"
        or not authenticated_user.get(
            "user_id"
        )
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Password changes require a "
                "database-backed BXK account."
            ),
        )

    try:
        result = change_user_password(
            session,
            user_id=authenticated_user[
                "user_id"
            ],
            current_password=(
                request_data.current_password
            ),
            new_password=(
                request_data.new_password
            ),
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "password_changed": True,
        **result,
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
