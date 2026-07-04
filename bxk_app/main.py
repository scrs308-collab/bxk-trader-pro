from bxk_app.live_market import live_engine
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from bxk_app.routes import router

app = FastAPI(
    title="BXK Trader Pro ",
    version="6.0"
)
live_engine.start()
app.include_router(router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def home():
    return FileResponse("static/index.html")
