"""Default-off production preview boundary; no broker or order transport."""
import os
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

PREVIEW_HTML = "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>BXK Workbench Preview</title><link rel=\"stylesheet\" href=\"/static/style.css?v=30\"></head><body><main style=\"max-width:960px;margin:40px auto;padding:24px\"><a href=\"/\">Back to dashboard</a><h1>Trade Workbench preview</h1><p>Owner preview. Order submission is unavailable.</p><p>Check the verified tastytrade connection belonging to your signed-in user. Quotes and order dry-runs are not yet available on this page.</p><button type=\"button\" id=\"checkConnection\">Check my SPXW expirations</button><p id=\"connectionStatus\" role=\"status\"></p><ul id=\"expirationList\"></ul><script src=\"/static/workbench-preview.js\" defer></script><p>The existing dashboard remains available through the link above.</p></main></body></html>"

def workbench_page(request: Request):
    if os.getenv("BXK_WORKBENCH_PREVIEW_ENABLED", "").strip().lower() != "true":
        raise HTTPException(404, "Not found")
    from bxk_app.authorization import require_owner
    require_owner(request)
    return HTMLResponse(PREVIEW_HTML, headers={
        "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow",
        "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'",
    })
