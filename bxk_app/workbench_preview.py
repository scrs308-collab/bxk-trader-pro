"""Default-off production preview boundary; no broker or order transport."""
import os
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

PREVIEW_HTML = "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>BXK Workbench Preview</title><link rel=\"stylesheet\" href=\"/static/style.css?v=30\"></head><body><main style=\"max-width:960px;margin:40px auto;padding:24px\"><a href=\"/\">Back to dashboard</a><h1>Trade Workbench preview</h1><p>Owner preview. Order submission is unavailable.</p><p>Check the verified tastytrade connection belonging to your signed-in user. Load bid/ask snapshots after checking your connection. Select a condor, review its four legs, then run the broker risk and buying-power check. No live order can be submitted.</p><button type=\"button\" id=\"checkConnection\">Check my SPXW expirations</button><p id=\"connectionStatus\" role=\"status\"></p><ul id=\"expirationList\"></ul><section><label>Expiration <select id=\"quoteExpiry\"></select></label><label>Minimum strike <input id=\"quoteMin\" type=\"number\" min=\"1\" step=\"5\"></label><label>Maximum strike <input id=\"quoteMax\" type=\"number\" min=\"1\" step=\"5\"></label><button id=\"loadQuotes\" type=\"button\" disabled>Load bid/ask quotes</button><p id=\"quoteStatus\" role=\"status\"></p><div id=\"quoteResults\"></div></section><section><h2>Combined condor analysis</h2><p>Enter your SPX reference and expected move in points. POP is a normal-distribution approximation, not broker POP. Fresh quotes are required; results exclude fees.</p><label>SPX reference <input id=\"analysisSpot\" type=\"number\" min=\"1\" step=\"0.01\"></label><label>Expected move (1 sigma) <input id=\"analysisMove\" type=\"number\" min=\"0.01\" step=\"0.01\"></label><label>Wing width <input id=\"analysisWidth\" type=\"number\" min=\"1\" max=\"100\" value=\"10\"></label><label>Minimum modeled POP (%) <input id=\"analysisPop\" type=\"number\" min=\"1\" max=\"99\" value=\"70\"></label><button id=\"analyzeCondors\" type=\"button\">Analyze condors</button><p id=\"analysisStatus\" role=\"status\"></p><div id=\"analysisResults\"></div></section><script src=\"/static/workbench-preview.js\" defer></script><p>The existing dashboard remains available through the link above.</p></main></body></html>"

def workbench_page(request: Request):
    if os.getenv("BXK_WORKBENCH_PREVIEW_ENABLED", "").strip().lower() != "true":
        raise HTTPException(404, "Not found")
    from bxk_app.authorization import require_owner
    require_owner(request)
    return HTMLResponse(PREVIEW_HTML, headers={
        "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow",
        "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'",
    })
