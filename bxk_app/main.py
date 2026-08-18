from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from bxk_app.auth_middleware import (
    enforce_bxk_authentication,
)
from bxk_app.routes import router


app = FastAPI(
    title="BXK Trader Pro",
    version="6.1",
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


@app.get("/")
def home():
    return FileResponse(
        "static/index.html"
    )
