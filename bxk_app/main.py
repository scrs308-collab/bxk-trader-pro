from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from bxk_app.routes import router

app = FastAPI(
    title="BXK Scanner V5",
    version="5.0"
)

app.include_router(router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def home():
    return FileResponse("static/index.html")
