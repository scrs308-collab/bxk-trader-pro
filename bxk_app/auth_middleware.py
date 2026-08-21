from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from bxk_app import config
from bxk_app.services.auth_service import (
    SESSION_COOKIE_NAME,
    verify_session_token,
)


PUBLIC_PATHS = {
    "/login",
    "/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/status",
}


async def enforce_bxk_authentication(
    request: Request,
    call_next,
):
    if not config.BXK_AUTH_ENABLED:
        return await call_next(request)

    path = request.url.path

    if path in PUBLIC_PATHS:
        return await call_next(request)

    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    session = (
        verify_session_token(token)
        if token
        else None
    )

    if session:
        request.state.bxk_user = session
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse(
            status_code=401,
            content={
                "detail":
                    "BXK authentication required."
            },
        )

    return RedirectResponse(
        url="/login",
        status_code=303,
    )
