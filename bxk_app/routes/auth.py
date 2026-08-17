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
    create_session_token,
    verify_credentials,
    verify_session_token,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    username: str
    password: str


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
