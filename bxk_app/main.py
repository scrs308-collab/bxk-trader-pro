import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from bxk_app.auth_middleware import (
    enforce_bxk_authentication,
)
from bxk_app.routes import router
from bxk_app.services.market_heartbeat_service import (
    run_market_heartbeat,
)
from bxk_app.services.overnight_alert_service import (
    run_overnight_alert_monitor,
)
from bxk_app.services.position_alert_service import (
    run_daytime_alert_monitor,
)
from bxk_app.services.sms_consent_service import (
    provision_sms_phones_from_environment,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pending_sms = (
            provision_sms_phones_from_environment()
        )

        if pending_sms:
            logger.info(
                "Provisioned %s pending SMS phone "
                "assignment(s).",
                len(pending_sms),
            )
    except Exception:
        logger.exception(
            "Pending SMS phone provisioning failed."
        )

    heartbeat_task = asyncio.create_task(
        run_market_heartbeat(),
        name="bxk-market-heartbeat",
    )

    app.state.market_heartbeat_task = (
        heartbeat_task
    )

    overnight_alert_task = (
        asyncio.create_task(
            run_overnight_alert_monitor(),
            name="bxk-overnight-sms-alerts",
        )
    )

    app.state.overnight_alert_task = (
        overnight_alert_task
    )

    daytime_alert_task = asyncio.create_task(
        run_daytime_alert_monitor(),
        name="bxk-daytime-sms-alerts",
    )

    app.state.daytime_alert_task = (
        daytime_alert_task
    )

    try:
        yield
    finally:
        daytime_alert_task.cancel()
        overnight_alert_task.cancel()
        heartbeat_task.cancel()

        try:
            await daytime_alert_task
        except asyncio.CancelledError:
            pass

        try:
            await overnight_alert_task
        except asyncio.CancelledError:
            pass

        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="BXK Trader Pro",
    version="6.1",
    lifespan=lifespan,
)


@app.middleware("http")
async def bxk_authentication_middleware(
    request,
    call_next,
):
    return await enforce_bxk_authentication(
        request,
        call_next,
    )


app.include_router(router)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


@app.get("/login")
def login_page():
    return FileResponse(
        "static/login.html"
    )


@app.get("/forgot-password")
def forgot_password_page():
    return FileResponse(
        "static/forgot-password.html"
    )


@app.get("/application-access")
def application_access_page():
    return FileResponse(
        "static/application-access.html"
    )


@app.get("/sms-opt-in")
def sms_opt_in_page():
    return FileResponse(
        "static/sms-opt-in.html"
    )


@app.get("/privacy")
def privacy_page():
    return FileResponse(
        "static/privacy.html"
    )


@app.get("/terms")
def terms_page():
    return FileResponse(
        "static/terms.html"
    )


@app.get("/change-password")
def change_password_page():
    return FileResponse(
        "static/change-password.html"
    )


@app.get("/subscription")
def subscription_page():
    return FileResponse(
        "static/subscription.html"
    )


@app.get("/")
def home(
    request: Request,
):
    state = request.query_params.get(
        "state"
    )

    code = request.query_params.get(
        "code"
    )

    error = request.query_params.get(
        "error"
    )

    if (
        state
        and (
            code
            or error
        )
    ):
        callback_url = (
            "/api/broker-connection/"
            "schwab/callback"
        )

        query = request.url.query

        if query:
            callback_url = (
                f"{callback_url}?{query}"
            )

        return RedirectResponse(
            url=callback_url,
            status_code=303,
        )

    return FileResponse(
        "static/index.html"
    )
