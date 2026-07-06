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