console.log("BXK Trader Pro Dashboard - Phase 2 UI");

const API_URL = "/api/recommend";

const el = (id) => document.getElementById(id);

function nowTime() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function setApiStatus(isOnline) {
  const apiStatus = el("apiStatus");

  if (isOnline) {
    apiStatus.textContent = "● LIVE";
    apiStatus.className = "status-pill online";
  } else {
    apiStatus.textContent = "● OFFLINE";
    apiStatus.className = "status-pill offline";
  }
}

function setScore(score) {
  const safeScore = Number(score) || 0;
  el("score").textContent = safeScore;
  el("scoreFill").style.width = `${Math.max(0, Math.min(100, safeScore))}%`;
}

function renderReasons(reasons) {
  const list = el("reasons");
  list.innerHTML = "";

  if (!Array.isArray(reasons) || reasons.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No scanner reasons returned.";
    list.appendChild(li);
    return;
  }

  reasons.forEach((reason) => {
    const li = document.createElement("li");
    li.textContent = reason;
    list.appendChild(li);
  });
}

function getStatusIcon(value) {
  const text = String(value || "").toLowerCase();

  if (text.includes("bull")) return "📈";
  if (text.includes("bear")) return "📉";
  if (text.includes("high") || text.includes("elevated")) return "⚡";
  if (text.includes("low")) return "🟢";
  if (text.includes("normal") || text.includes("neutral")) return "⚪";
  if (text.includes("avoid") || text.includes("no")) return "🔴";
  if (text.includes("trade") || text.includes("good")) return "🟢";

  return "•";
}

function updateDashboard(data) {
  el("recommendation").textContent = data.recommendation ?? "--";
  el("confidence").textContent = `Confidence: ${data.confidence ?? "--"}`;

  setScore(data.score);

  el("trade").textContent = `${getStatusIcon(data.trade)} ${data.trade ?? "--"}`;
  el("trend").textContent = `${getStatusIcon(data.trend)} ${data.trend ?? "--"}`;
  el("vixState").textContent = `${getStatusIcon(data.vix_state)} ${data.vix_state ?? "--"}`;
  el("expectedMove").textContent = `${getStatusIcon(data.expected_move_state)} ${data.expected_move_state ?? "--"}`;
  el("ivRank").textContent = `${getStatusIcon(data.iv_rank_state)} ${data.iv_rank_state ?? "--"}`;

  renderReasons(data.reasons);
  
  const opportunity = data.opportunity || {};

  el("strategyName").textContent =
    opportunity.strategy ?? "--";

  el("spxPrice").textContent =
    opportunity.spx_price ?? "--";

  el("expectedMovePoints").textContent =
    opportunity.expected_move ?? "--";

  el("sellPut").textContent =
    opportunity.sell_put ?? "--";

  el("buyPut").textContent =
    opportunity.buy_put ?? "--";

  el("sellCall").textContent =
    opportunity.sell_call ?? "--";

  el("buyCall").textContent =
    opportunity.buy_call ?? "--";

  el("targetCredit").textContent =
    opportunity.target_credit ?? "--";

  el("pop").textContent =
    opportunity.pop ? `${opportunity.pop}%` : "--";

  el("maxRisk").textContent =
    opportunity.max_risk
        ? `$${opportunity.max_risk}`
        : "--";

  el("expectedProfit").textContent =
    opportunity.expected_profit
        ? `$${opportunity.expected_profit}`
        : "--";

  el("riskLevel").textContent =
    opportunity.risk_level ?? "--";

  el("tradeScore").textContent =
    opportunity.trade_score ?? "--";

  el("tradeConfidence").textContent =
    opportunity.confidence ?? "--";

  el("putBuffer").textContent =
    opportunity.put_buffer ?? "--";

  el("callBuffer").textContent =
    opportunity.call_buffer ?? "--";

  el("tradeSource").textContent =
    opportunity.source ?? "--";
    
      el("liveCredit").textContent =
    opportunity.live_credit ?? "--";

  el("putCredit").textContent =
    opportunity.put_credit ?? "--";

  el("callCredit").textContent =
    opportunity.call_credit ?? "--";

  el("returnOnRisk").textContent =
    opportunity.return_on_risk
      ? `${opportunity.return_on_risk}%`
      : "--";

  el("candidatesEvaluated").textContent =
    opportunity.candidates_evaluated ?? "--";
}    

async function fetchRecommendation() {
  try { 
    const response = await fetch(API_URL);

    if (!response.ok) {
      throw new Error(`API error ${response.status}`);
    }

    const data = await response.json();

    updateDashboard(data);
    setApiStatus(true);
  } catch (error) {
    console.error("Dashboard fetch failed:", error);
    setApiStatus(false);
    el("recommendation").textContent = "API Offline";
  }
}

function updateClock() {
  el("clock").textContent = nowTime();
}

fetchRecommendation();
updateClock();

setInterval(fetchRecommendation, 30000);
setInterval(updateClock, 1000);

async function loadBestTrade() {
  const card = document.getElementById("bestTradeCard");

  try {
    const response = await fetch("/api/best-trade");
    const data = await response.json();
    const trade = data.best_trade;

    if (!trade) {
      card.innerHTML = `
        <div class="hero-header">
          <div>
            <div class="eyebrow">Today's Best Trade</div>
            <h1>No Trade Available</h1>
          </div>
          <div class="hero-badge no-trade">NO TRADE</div>
        </div>
        <p>${data.reason || "The trade engine did not return a setup."}</p>
      `;
      return;
    }
    console.log(trade);
    const isDemo = data.status === "DEMO";
   const recommendation =
     trade.market_regime === "TRADE"
       ? "ENTER TRADE"
    :   "NO TRADE";
   const badgeClass =
  isDemo
    ? "demo"
    : trade.market_regime === "TRADE"
      ? "enter"
      : "no-trade";

    const tradeScore = trade.trade_score || 0;
    const pop = trade.pop || 84;
    const reasons = (trade.reasons || [])
    .map(reason => `<span>✓ ${reason}</span>`)
    .join("");

    card.innerHTML = `
      <div class="hero-header">
        <div>
          <div class="eyebrow">Today's Best Trade</div>
          <h1>${trade.strategy}</h1>
          <div class="subline">
            SPX ${trade.spx_price} • ${trade.dte} DTE • Expected Move ±${trade.expected_move}
          </div>
        </div>

        <div class="hero-badge ${badgeClass}">
          ${recommendation}
        </div>
      </div>

      <div class="hero-main">
        <div class="score-block">
          <div class="score-number">${tradeScore}</div>
          <div class="score-label">Trade Score</div>
          <div class="score-bar">
            <div class="score-fill" style="width:${Math.min(tradeScore, 100)}%"></div>
          </div>
        </div>

        <div class="legs-grid">
          <div class="option-leg sell">
            <span>SELL</span>
            <strong>${trade.sell_call} CALL</strong>
          </div>
          <div class="option-leg buy">
            <span>BUY</span>
            <strong>${trade.buy_call} CALL</strong>
          </div>
          <div class="option-leg sell">
            <span>SELL</span>
            <strong>${trade.sell_put} PUT</strong>
          </div>
          <div class="option-leg buy">
            <span>BUY</span>
            <strong>${trade.buy_put} PUT</strong>
          </div>
        </div>
      </div>
          
        <div class="why-pills">
           ${reasons}
      </div>
      <div class="metric-strip">
        <div>
          <span>Credit</span>
          <strong>$${trade.credit}</strong>
        </div>
        <div>
          <span>Max Profit</span>
          <strong>$${trade.max_profit}</strong>
        </div>
        <div>
          <span>Max Risk</span>
          <strong>$${trade.max_risk}</strong>
        </div>
        <div>
          <span>POP</span>
          <strong>${pop}%</strong>
        </div>
        <div>
          <span>Risk / Reward</span>
          <strong>${trade.risk_reward}</strong>
        </div>
        <div>
          <span>Wing</span>
          <strong>${trade.wing_width}</strong>
        </div>
      </div>

     
    `;
  } catch (error) {
    card.innerHTML = `
      <div class="hero-header">
        <div>
          <div class="eyebrow">Today's Best Trade</div>
          <h1>Engine Error</h1>
        </div>
        <div class="hero-badge no-trade">ERROR</div>
      </div>
      <p>Could not load the best-trade engine.</p>
    `;
  }
}

loadBestTrade();
setInterval(loadBestTrade, 60000);