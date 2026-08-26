import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    try:
        yield
    finally:
        overnight_alert_task.cancel()
        heartbeat_task.cancel()

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


@app.get("/")
def home():
    return FileResponse(
        "static/index.html"
    )
