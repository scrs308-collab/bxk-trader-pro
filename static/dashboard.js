const dashboard = document.getElementById("dashboard");

function nowTime() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
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
      <div><span>Time</span><strong id="marketClock">${nowTime()}</strong></div>
      <div><span>Status</span><strong id="marketStatus">LIVE</strong></div>
    </div>

    <div class="status-pill trade">TRADE</div>
  </header>

  <section class="hero-grid">
    <div class="panel health-panel">
      <h2>Market Health</h2>
      <div class="meter">
        <div class="meter-fill" style="width: 84%;"></div>
      </div>
      <div class="meter-label">84% Healthy</div>
    </div>

    <div class="panel action-panel">
      <h2>Action Now</h2>
      <div class="big-signal trade">SELL IRON CONDOR</div>
      <p class="muted">Confidence 100%</p>
    </div>

    <div class="panel score-panel">
      <h2>Trade Quality</h2>
      <div class="score-circle">100</div>
      <p>Grade A</p>
    </div>
  </section>

  <section class="grid cards-5">
    <div class="card good"><span>Trend</span><strong>MIXED</strong><small>Market structure neutral</small></div>
    <div class="card good"><span>VIX</span><strong>IDEAL</strong><small>Volatility favorable</small></div>
    <div class="card good"><span>Expected Move</span><strong>HEALTHY</strong><small>Premium environment OK</small></div>
    <div class="card good"><span>IV Rank</span><strong>GOOD</strong><small>Option premium acceptable</small></div>
    <div class="card warn"><span>Time Window</span><strong>WAIT</strong><small>Opening range not confirmed</small></div>
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
        <tbody>
          <tr><td>1</td><td>Iron Condor</td><td>100</td><td><span class="badge good-badge">High</span></td></tr>
          <tr><td>2</td><td>Butterfly</td><td>70</td><td><span class="badge mid-badge">Medium</span></td></tr>
          <tr><td>3</td><td>Debit Call Spread</td><td>45</td><td><span class="badge low-badge">Low</span></td></tr>
          <tr><td>4</td><td>Debit Put Spread</td><td>45</td><td><span class="badge low-badge">Low</span></td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>Decision Reasons</h2>
      <ul class="checklist">
        <li>VIX ideal</li>
        <li>Expected move healthy</li>
        <li>IV rank good</li>
        <li>Premium selling environment acceptable</li>
      </ul>
    </div>
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
    const response = await fetch("/api/market-header");
    const data = await response.json();

    document.getElementById("spxPrice").textContent = data.spx ?? "--";
    document.getElementById("vixPrice").textContent = data.vix ?? "--";
    document.getElementById("vix1dPrice").textContent = data.vix1d ?? "--";
    document.getElementById("marketClock").textContent = data.server_time ?? nowTime();
    document.getElementById("marketStatus").textContent = data.market_status ?? "LIVE";
  } catch (error) {
    console.error("Market header failed:", error);
    document.getElementById("marketClock").textContent = nowTime();
  }
}

loadMarketHeader();
setInterval(loadMarketHeader, 5000);
async function loadRecommendation() {
  try {
    const response = await fetch("/recommend");
    const data = await response.json();

    console.log("Recommendation data:", data);

  } catch (error) {
    console.error("Recommendation failed:", error);
  }
}

async function loadRecommendation() {
  try {
    const response = await fetch("/recommend");
    const data = await response.json();

    document.querySelector(".status-pill").textContent = data.trade ?? "WAIT";
    document.querySelector(".big-signal").textContent =
      data.recommendation ?? data.trade ?? "WAIT";

    document.querySelector(".score-circle").textContent =
      data.confidence ?? "--";

    document.querySelector(".score-panel p").textContent =
      `Score ${data.score ?? "--"} / Confidence ${data.confidence ?? "--"}%`;

    document.querySelector(".card:nth-child(1) strong").textContent =
      data.trend ?? "--";

    document.querySelector(".card:nth-child(2) strong").textContent =
      data.vix_state ?? "--";

    document.querySelector(".card:nth-child(3) strong").textContent =
      data.expected_move_state ?? "--";

    document.querySelector(".card:nth-child(4) strong").textContent =
      data.iv_rank_state ?? "--";

  } catch (error) {
    console.error("Recommendation failed:", error);
  }
}

loadRecommendation();
setInterval(loadRecommendation, 10000);