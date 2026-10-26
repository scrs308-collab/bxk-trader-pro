"""Isolated staging UI with its own login; never imports trading, DB or broker modules."""
import base64
from contextlib import asynccontextmanager
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def reconciliation_lifespan(application):
    # This ledger contains synthetic attempts only; startup never contacts a broker.
    from staging_reconciliation import Ledger
    try:
        Ledger().recover_inflight()
        application.state.reconciliation_ready = True
    except HTTPException:
        application.state.reconciliation_ready = False
    yield


app = FastAPI(title="BXK Trade Workbench Staging", lifespan=reconciliation_lifespan)
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
    return {"status": "ok", "mode": "isolated-staging", "auth_configured": _configured(), "market_data_configured": bool(os.getenv("TASTYTRADE_CLIENT_SECRET") and os.getenv("TASTYTRADE_REFRESH_TOKEN"))}


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


@app.get("/api/workbench/expirations")
def workbench_expirations():
    """Owner-authenticated, read-only SPXW expiration discovery."""
    from staging_market_data import get_expirations
    return get_expirations()


@app.get("/api/workbench/spx-reference")
def workbench_spx_reference():
    """Fetch a timestamp-verified SPX index reference quote from tastytrade."""
    from staging_market_data import get_spx_reference
    return get_spx_reference()


@app.get("/api/workbench/quotes")
def workbench_quotes(
    expiration: str = Query(..., pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    min_strike: float = Query(..., gt=0),
    max_strike: float = Query(..., gt=0),
):
    """Read-only, bounded bid/ask retrieval. No order/account methods."""
    from staging_market_data import get_quotes
    return get_quotes(expiration, min_strike, max_strike)


class PreviewLeg(BaseModel):
    symbol: str
    action: str


class WorkbenchDryRun(BaseModel):
    legs: list[PreviewLeg]
    quantity: int = Field(1, ge=1, le=1)
    limit_price: float = Field(..., gt=0, le=100)


@app.post("/api/workbench/order-dry-run")
def workbench_order_dry_run(payload: WorkbenchDryRun):
    """Authenticated broker dry-run only; never creates or submits an order."""
    from staging_order_preview import preview
    return preview(payload)


class ConfirmationRequest(WorkbenchDryRun):
    confirmation_token: str = Field(..., min_length=20, max_length=128)


@app.post("/api/workbench/confirmation-issue")
def issue_confirmation(payload: WorkbenchDryRun):
    """Re-run broker validation and issue a short-lived simulation-only token."""
    from staging_order_preview import preview
    from staging_confirmation import issue
    result = preview(payload)
    return issue(payload, result)


@app.post("/api/workbench/confirmation-consume")
def consume_confirmation(payload: ConfirmationRequest):
    """Consume one-time token; intentionally has no broker order submission."""
    from staging_confirmation import consume
    return consume(payload, payload.confirmation_token)


@app.post("/api/workbench/confirmation-receipt")
def confirmation_receipt(payload: ConfirmationRequest):
    """Owner-authenticated persisted simulation evidence, without broker access."""
    from staging_confirmation import receipt
    return receipt(payload, payload.confirmation_token)


@app.post("/api/workbench/reconciliation-rehearsal")
def reconciliation_rehearsal():
    """Owner-authenticated synthetic fault scenarios; no external network calls."""
    from staging_reconciliation_rehearsal import run
    return run()


@app.get("/api/workbench/reconciliation-rehearsal/{intent}")
def reconciliation_rehearsal_receipt(intent: str):
    from uuid import UUID
    from staging_reconciliation_rehearsal import receipt
    try:
        UUID(intent)
    except ValueError:
        raise HTTPException(400, "Invalid rehearsal receipt") from None
    return receipt(intent)


@app.post("/api/workbench/reconciliation-rehearsal/{intent}/attempt")
def reconciliation_rehearsal_attempt(intent: str):
    """Synthetic duplicate-attempt test. Always has no broker transport."""
    from staging_reconciliation import Ledger
    Ledger().begin_attempt(intent)
    return {"synthetic_data": True, "submitted": False, "attempt_reserved": True}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def disabled_api(path: str):
    return JSONResponse(
        {"detail": "Isolated staging: market data and trading APIs are disabled."},
        status_code=503,
    )
