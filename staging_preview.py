"""Isolated staging UI with its own login; never imports trading, DB or broker modules."""
import base64
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent / "static"
app = FastAPI(title="BXK Trade Workbench Staging")
COOKIE = "bxk_staging_session"
TTL = 43200


def _configured():
    return bool(os.getenv("BXK_APP_USERNAME") and os.getenv("BXK_APP_PASSWORD_HASH")
                and os.getenv("BXK_SESSION_SECRET") and os.getenv("BXK_AUTH_ENABLED", "").lower() == "true")


def _verify_password(password):
    try:
        scheme, count, salt, digest = os.environ["BXK_APP_PASSWORD_HASH"].split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        rounds = int(count)
        if not 100000 <= rounds <= 2000000:
            return False
        raw_salt = base64.urlsafe_b64decode(salt)
        expected = base64.urlsafe_b64decode(digest)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), raw_salt, rounds)
        return hmac.compare_digest(actual, expected)
    except (KeyError, ValueError, TypeError):
        return False


def _token():
    expiry = int(time.time()) + TTL
    nonce = secrets.token_urlsafe(18)
    payload = f"{expiry}:{nonce}"
    signature = hmac.new(os.environ["BXK_SESSION_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def _authorized(request):
    token = request.cookies.get(COOKIE, "")
    try:
        expiry, nonce, signature = token.split(":", 2)
        if int(expiry) <= time.time():
            return False
        payload = f"{expiry}:{nonce}"
        expected = hmac.new(os.environ["BXK_SESSION_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (KeyError, ValueError):
        return False


@app.middleware("http")
async def staging_auth(request: Request, call_next):
    path = request.url.path
    if path == "/health":
        return await call_next(request)
    if not _configured():
        return JSONResponse({"detail": "Staging authentication is not fully configured."}, status_code=503)
    if path in {"/login", "/api/auth/login"}:
        return await call_next(request)
    if not _authorized(request):
        if path.startswith("/api/") or path.startswith("/static/"):
            return JSONResponse({"detail": "Sign in required."}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


app.mount("/static", StaticFiles(directory=str(ROOT)), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "mode": "isolated-staging", "auth_configured": _configured()}


@app.get("/login")
def login_page():
    return FileResponse(ROOT / "login.html", headers={"Cache-Control": "no-store"})


class Credentials(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(credentials: Credentials):
    username = os.getenv("BXK_APP_USERNAME", "")
    # Always perform password verification before comparing username.
    password_ok = _verify_password(credentials.password)
    username_ok = hmac.compare_digest(credentials.username.encode(), username.encode())
    if not (username_ok and password_ok):
        return JSONResponse({"detail": "Invalid username or password."}, status_code=401)
    response = JSONResponse({"authenticated": True, "must_change_password": False})
    response.set_cookie(COOKIE, _token(), max_age=TTL, httponly=True, secure=True, samesite="strict", path="/")
    return response


@app.get("/api/auth/status")
def auth_status():
    return {"enabled": True, "configured": True, "authenticated": True,
            "username": os.getenv("BXK_APP_USERNAME"), "role": "OWNER"}


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(COOKIE, path="/")
    return response


@app.get("/")
def index():
    return FileResponse(ROOT / "index.html", headers={"Cache-Control": "no-store"})


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def disabled_api(path: str):
    return JSONResponse(
        {"detail": "Isolated staging: market data and trading APIs are disabled."},
        status_code=503,
    )
