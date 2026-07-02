from fastapi.responses import HTMLResponse
from fastapi import APIRouter

from bxk_app.scoring import score_market

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "OK"
    }


@router.get("/recommend")

def recommend():
    market_score = score_market()

    return {
        "trade": market_score.market_regime,
        "confidence": market_score.confidence,
        "score": market_score.score,
        "trend": market_score.trend,
        "vix_state": market_score.vix_state,
        "expected_move_state": market_score.expected_move_state,
        "iv_rank_state": market_score.iv_rank_state,
        "recommendation": market_score.recommendation,
        "reasons": market_score.reasons,
    }
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
    <html>
    <head>
        <title>BXK Scanner V5</title>
    </head>

    <body style="font-family:Arial;background:#101722;color:white;padding:30px;">

        <h1>BXK Scanner V5</h1>

        <div id="results">
            Loading...
        </div>

        <script>

        fetch("/recommend")
        .then(r=>r.json())
        .then(data=>{

            document.getElementById("results").innerHTML=`

            <h2>${data.trade}</h2>

            <p><b>Confidence:</b> ${data.confidence}%</p>

            <p><b>Score:</b> ${data.score}</p>

            <p><b>Trend:</b> ${data.trend}</p>

            <p><b>VIX:</b> ${data.vix_state}</p>

            <p><b>Expected Move:</b> ${data.expected_move_state}</p>

            <p><b>IV Rank:</b> ${data.iv_rank_state}</p>

            <p><b>Recommendation:</b> ${data.recommendation}</p>

            <h3>Reasons</h3>

            <ul>

            ${data.reasons.map(x=>`<li>${x}</li>`).join("")}

            </ul>

            `

        });

        </script>

    </body>

    </html>

    """