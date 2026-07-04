console.log("BXK Trader Pro Dashboard v5.1 Loaded");

const dashboard = document.getElementById("dashboard");

function nowTime() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function safe(value, fallback = "--") {
  return value ?? fallback;
}

function normalizeTrade(value) {
  const text = String(value ?? "WAIT").toUpperCase();

  if (text.includes("TRADE")) return "TRADE";
  if (text.includes("WAIT")) return "WAIT";
  if (text.includes("NO")) return "NO TRADE";

  return text;
}

function healthPercent(score) {
  const numeric = Number(score ?? 0);
  return Math.max(0, Math.min(100, numeric * 28));
}

function badgeClass(confidence) {
  if (confidence === "High") return "good-badge";
  if (confidence === "Medium") return "mid-badge";
  return "low-badge";
}

dashboard.innerHTML = `
<div class="app">
  <header class="topbar">
    <div>
      <h1>BXK Trader Pro</h1>
      <p>Professional SPX Options Intelligence</p>
    </div>

  <div class="market-strip">
    <div><span>SPX</span><strong id="spxPrice">--</strong></div>

    <div><span>VIX</span><strong id="vixPrice">--</strong></div>

    <div><span>VIX1D</span><strong id="vix1dPrice">--</strong></div>

    <div><span>Expected Move</span><strong id="expectedMove">--</strong></div>

    <div><span>Time</span><strong id="marketClock">${nowTime()}</strong></div>

    <div><span>Status</span><strong id="marketStatus">--</strong></div>
  </div>

    <div id="tradePill" class="status-pill wait">WAIT</div>
  </header>

  <section class="hero-grid">
    <div class="panel health-panel">
      <h2>Market Health</h2>
      <div class="meter">
        <div id="healthFill" class="meter-fill" style="width: 0%;"></div>
      </div>
      <div id="healthLabel" class="meter-label">-- Healthy</div>
    </div>

    <div class="panel action-panel">
      <h2>Action Now</h2>
      <div id="actionSignal" class="big-signal wait">Loading...</div>
      <p id="actionConfidence" class="muted">Confidence --</p>
    </div>

    <div class="panel score-panel">
      <h2>Trade Quality</h2>
      <div id="scoreCircle" class="score-circle">--</div>
      <p id="scoreText">Score -- / Confidence --</p>
    </div>
  </section>

  <section class="grid cards-5">
    <div class="card good"><span>Trend</span><strong id="trendState">--</strong><small>Market structure</small></div>
    <div class="card good"><span>VIX</span><strong id="vixState">--</strong><small>Volatility condition</small></div>
    <div class="card good"><span>Expected Move</span><strong id="expectedMoveState">--</strong><small>Premium environment</small></div>
    <div class="card good"><span>IV Rank</span><strong id="ivRankState">--</strong><small>Option premium</small></div>
    <div class="card warn"><span>Time Window</span><strong id="timeWindowState">WAIT</strong><small>Opening range not confirmed</small></div>
  </section>

  <section class="two-col">
    <div class="panel">
      <h2>Top Strategies Today</h2>
      <table>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Strategy</th>
            <th>Score</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody id="strategyRows">
          <tr><td colspan="4">Loading strategies...</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>Decision Reasons</h2>
      <ul id="decisionReasons" class="checklist">
        <li>Loading decision reasons...</li>
      </ul>
    </div>
  </section>
  <section class="panel narrative-panel">
  <h2>Market Narrative</h2>
  <p id="marketNarrative">Loading market narrative...</p>

</section>
  <section class="panel position-panel">
    <h2>Position Monitor</h2>
    <div class="position-grid">
      <div><span>Current Position</span><strong>No active trade</strong></div>
      <div><span>P/L</span><strong>--</strong></div>
      <div><span>Short Put Buffer</span><strong>--</strong></div>
      <div><span>Short Call Buffer</span><strong>--</strong></div>
      <div><span>Exit Signal</span><strong>WAIT</strong></div>
    </div>
  </section>
</div>
`;

async function loadMarketHeader() {
  try {
    const response = await fetch("/api/live-market");
    const data = await response.json();

    document.getElementById("spxPrice").textContent = safe(data.spx);
    document.getElementById("vixPrice").textContent = safe(data.vix);
    document.getElementById("vix1dPrice").textContent = safe(data.vix1d);
    document.getElementById("marketClock").textContent = safe(data.server_time, nowTime());
    document.getElementById("expectedMove").textContent = "±" + safe(data.expected_move);

    const status = document.getElementById("marketStatus");
    const marketStatus = safe(data.market_status, "UNKNOWN");

    status.textContent = marketStatus;
    status.className = "";

    switch (marketStatus) {
      case "LIVE":
        status.classList.add("green");
        break;

      case "PRE-MARKET":
        status.classList.add("yellow");
        break;

      case "AFTER HOURS":
      case "CLOSED":
        status.classList.add("red");
        break;

      default:
        status.classList.add("yellow");
        break;
    }
  } catch (error) {
    console.error("Market header failed:", error);
    document.getElementById("marketClock").textContent = nowTime();
  }
}

async function loadStatus() {
  try {
    const response = await fetch("/recommend");
    const data = await response.json();

    const trade = normalizeTrade(data.trade);
    const confidence = Number(data.confidence ?? 0);
    const health = healthPercent(data.score);

    const tradePill = document.getElementById("tradePill");
    const actionSignal = document.getElementById("actionSignal");

    tradePill.textContent = trade;
    tradePill.className = "status-pill";
    tradePill.classList.add(trade === "TRADE" ? "trade" : "wait");

    actionSignal.textContent = safe(data.recommendation, trade);
    actionSignal.className = "big-signal";
    actionSignal.classList.add(trade === "TRADE" ? "trade" : "wait");

    document.getElementById("actionConfidence").textContent = `Confidence ${confidence}%`;

    document.getElementById("scoreCircle").textContent = confidence || "--";
    document.getElementById("scoreText").textContent =
      `Score ${safe(data.score)} / Confidence ${confidence}%`;

    document.getElementById("healthFill").style.width = `${health}%`;
    document.getElementById("healthLabel").textContent = `${health}% Healthy`;

    document.getElementById("trendState").textContent = safe(data.trend);
    document.getElementById("vixState").textContent = safe(data.vix_state);
    document.getElementById("expectedMoveState").textContent = safe(data.expected_move_state);
    document.getElementById("ivRankState").textContent = safe(data.iv_rank_state);

    renderStrategies(data.strategies ?? []);
    renderReasons(data.reasons ?? []);
  } catch (error) {
    console.error("Status failed:", error);
  }
}

function renderStrategies(strategies) {
  const tbody = document.getElementById("strategyRows");

  if (!strategies.length) {
    tbody.innerHTML = `<tr><td colspan="4">No strategy data available</td></tr>`;
    return;
  }

  tbody.innerHTML = strategies
    .map((item, index) => {
      const confidence = safe(item.confidence);

      return `
        <tr>
          <td>${index + 1}</td>
          <td>${safe(item.name)}</td>
          <td>${safe(item.score)}</td>
          <td><span class="badge ${badgeClass(confidence)}">${confidence}</span></td>
        </tr>
      `;
    })
    .join("");
}

function renderReasons(reasons) {
  const list = document.getElementById("decisionReasons");

  if (!reasons.length) {
    list.innerHTML = `<li>No decision reasons available</li>`;
    return;
  }

  list.innerHTML = reasons.map((reason) => `<li>${reason}</li>`).join("");
}
async function loadMarketBrief() {
  try {
    const response = await fetch("/api/market-brief");
    const data = await response.json();

    document.getElementById("marketNarrative").textContent =
      data.summary ?? "No market narrative available.";
  } catch (error) {
    console.error("Market brief failed:", error);
    document.getElementById("marketNarrative").textContent =
      "Market narrative unavailable.";
  }
}
loadMarketHeader();
loadStatus();
loadMarketBrief();

setInterval(loadMarketHeader, 5000);
setInterval(loadStatus, 10000);
setInterval(loadMarketBrief, 15000);