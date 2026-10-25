"""Isolated, read-only BXK staging UI. No production app, DB, brokers or background jobs."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent / "static"
app = FastAPI(title="BXK Trade Workbench Staging")
app.mount("/static", StaticFiles(directory=str(ROOT)), name="static")

@app.get("/health")
def health():
    return {"status": "ok", "mode": "isolated-staging"}

@app.get("/")
def index():
    return FileResponse(ROOT / "index.html", headers={"Cache-Control": "no-store"})

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def disabled_api(path: str):
    return JSONResponse(
        {"detail": "Isolated staging: live market data, authentication, billing and trading APIs are disabled."},
        status_code=503,
    )
