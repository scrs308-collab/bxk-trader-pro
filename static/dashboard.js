console.log("BXK Trader Pro Dashboard - V9");

const API_URL = "/api/recommend";
const BEST_TRADE_URL = "/api/best-trade";

const el = (id) => document.getElementById(id);


/* =========================================================
   GENERAL HELPERS
========================================================= */

function setText(id, value, fallback = "--") {
  const element = el(id);

  if (!element) {
    return;
  }

  const isMissing =
    value === null ||
    value === undefined ||
    value === "";

  element.textContent = isMissing
    ? fallback
    : value;
}


function safeNumber(value, fallback = 0) {
  const number = Number(value);

  return Number.isFinite(number)
    ? number
    : fallback;
}


function nowTime() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}


function formatMoney(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  return `$${number.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}


function formatNumber(value, decimals = 2) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  return number.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}


/* =========================================================
   API STATUS
========================================================= */

function setApiStatus(isOnline) {
  const apiStatus = el("apiStatus");

  if (!apiStatus) {
    return;
  }

  if (isOnline) {
    apiStatus.textContent = "● LIVE";
    apiStatus.className = "status-pill online";
  } else {
    apiStatus.textContent = "● OFFLINE";
    apiStatus.className = "status-pill offline";
  }
}


/* =========================================================
   MARKET SCORE
========================================================= */

function setScore(score) {
  const safeScore = Math.max(
    0,
    Math.min(100, safeNumber(score)),
  );

  setText("score", Math.round(safeScore));

  const scoreFill = el("scoreFill");

  if (scoreFill) {
    scoreFill.style.width = `${safeScore}%`;
  }
}


/* =========================================================
   REASONS
========================================================= */

function renderReasons(reasons) {
  const list = el("reasons");

  if (!list) {
    return;
  }

  list.innerHTML = "";

  if (!Array.isArray(reasons) || reasons.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No scanner reasons returned.";
    list.appendChild(li);
    return;
  }

  reasons.forEach((reason) => {
    const li = document.createElement("li");

    li.textContent =
      typeof reason === "string"
        ? reason
        : reason.reason || "Unknown reason";

    list.appendChild(li);
  });
}


/* =========================================================
   STATUS ICONS
========================================================= */

function getStatusIcon(value) {
  const text = String(value || "").toLowerCase();

  if (text.includes("bull")) return "📈";
  if (text.includes("bear")) return "📉";

  if (
    text.includes("ideal") ||
    text.includes("healthy") ||
    text.includes("good") ||
    text.includes("trade")
  ) {
    return "🟢";
  }

  if (
    text.includes("outside") ||
    text.includes("avoid") ||
    text.includes("no trade")
  ) {
    return "🔴";
  }

  if (
    text.includes("high") ||
    text.includes("elevated")
  ) {
    return "⚡";
  }

  if (text.includes("low")) return "🟡";

  if (
    text.includes("normal") ||
    text.includes("neutral") ||
    text.includes("mixed")
  ) {
    return "⚪";
  }

  if (text.includes("wait")) return "●";

  return "•";
}


/* =========================================================
   BXK MARKET READINESS
========================================================= */

function updateThermometer(score, data = {}) {
  const safeScore = Math.max(
    0,
    Math.min(100, safeNumber(score)),
  );

  setText(
    "thermoValue",
    `${Math.round(safeScore)}%`,
  );

  const pointer = el("thermoPointer");

  if (pointer) {
    pointer.style.left = `${safeScore}%`;
  }

  const status = el("thermoStatus");

  if (status) {
    status.classList.remove(
      "wait",
      "caution",
      "warming",
      "ready",
    );
  }

  if (safeScore >= 90) {
    setText(
      "thermoStatus",
      "TRADE WINDOW OPEN",
    );

    setText(
      "thermoMessage",
      "Market conditions support entry.",
    );

    status?.classList.add("ready");
  } else if (safeScore >= 75) {
    setText(
      "thermoStatus",
      "ALMOST READY",
    );

    setText(
      "thermoMessage",
      "Waiting for final confirmation.",
    );

    status?.classList.add("warming");
  } else if (safeScore >= 50) {
    setText(
      "thermoStatus",
      "WARMING UP",
    );

    setText(
      "thermoMessage",
      "Market conditions are improving.",
    );

    status?.classList.add("warming");
  } else if (safeScore >= 25) {
    setText(
      "thermoStatus",
      "CAUTION",
    );

    setText(
      "thermoMessage",
      "Some conditions support trading, but entry is not ready.",
    );

    status?.classList.add("caution");
  } else {
    setText(
      "thermoStatus",
      "WAIT",
    );

    setText(
      "thermoMessage",
      "Market not ready.",
    );

    status?.classList.add("wait");
  }

  renderMarketBlockers(data);
}


function renderMarketBlockers(data) {
  const box = el("thermoBlockers");

  if (!box) {
    return;
  }

  const vixState = String(
    data.vix_state || "",
  ).toUpperCase();

  const expectedMoveState = String(
    data.expected_move_state || "",
  ).toUpperCase();

  const ivRankState = String(
    data.iv_rank_state || "",
  ).toUpperCase();

  const trend = String(
    data.trend || "",
  ).toUpperCase();

  const conditions = [
    {
      label: "VIX in preferred range",
      passed: vixState === "IDEAL",
    },
    {
      label: "Expected move is healthy",
      passed: expectedMoveState === "HEALTHY",
    },
    {
      label: "IV rank supports premium selling",
      passed: ivRankState === "GOOD",
    },
    {
      label: "Trend is identified",
      passed:
        trend !== "" &&
        trend !== "UNKNOWN",
    },
  ];

  box.innerHTML = conditions
    .map((condition) => {
      const className = condition.passed
        ? "passed"
        : "blocked";

      const icon = condition.passed
        ? "✓"
        : "✕";

      return `
        <div class="thermo-condition ${className}">
          <span class="condition-icon">${icon}</span>
          <span>${condition.label}</span>
        </div>
      `;
    })
    .join("");
}


/* =========================================================
   MAIN MARKET DASHBOARD
========================================================= */

function updateDashboard(data) {
  setText(
    "recommendation",
    data.recommendation,
  );

  setText(
    "confidence",
    `Confidence: ${data.confidence ?? "--"}`,
  );

  setScore(data.score);

  updateThermometer(
    data.score,
    data,
  );

  setText(
    "trade",
    `${getStatusIcon(data.trade)} ${
      data.trade ?? "--"
    }`,
  );

  setText(
    "trend",
    `${getStatusIcon(data.trend)} ${
      data.trend ?? "--"
    }`,
  );

  setText(
    "vixState",
    `${getStatusIcon(data.vix_state)} ${
      data.vix_state ?? "--"
    }`,
  );

  setText(
    "expectedMove",
    `${getStatusIcon(data.expected_move_state)} ${
      data.expected_move_state ?? "--"
    }`,
  );

  setText(
    "ivRank",
    `${getStatusIcon(data.iv_rank_state)} ${
      data.iv_rank_state ?? "--"
    }`,
  );

  renderReasons(data.reasons);

  setText(
    "lastUpdate",
    data.timestamp || nowTime(),
  );

  updateOpportunityCard(data);
  updateChecklist(data);
}


/* =========================================================
   LEGACY OPPORTUNITY CARD
========================================================= */

function updateOpportunityCard(data) {
  const opportunity =
    data.opportunity || {};

  setText(
    "strategyName",
    opportunity.strategy,
  );

  setText(
    "spxPrice",
    formatNumber(opportunity.spx_price),
  );

  setText(
    "expectedMovePoints",
    formatNumber(opportunity.expected_move),
  );

  setText(
    "sellPut",
    opportunity.sell_put,
  );

  setText(
    "buyPut",
    opportunity.buy_put,
  );

  setText(
    "sellCall",
    opportunity.sell_call,
  );

  setText(
    "buyCall",
    opportunity.buy_call,
  );

  setText(
    "targetCredit",
    formatNumber(
      opportunity.target_credit ??
      opportunity.live_credit,
    ),
  );

  setText(
    "pop",
    Number.isFinite(Number(opportunity.pop))
      ? `${formatNumber(opportunity.pop, 1)}%`
      : "--",
  );

  setText(
    "maxRisk",
    formatMoney(opportunity.max_risk),
  );

  setText(
    "expectedProfit",
    formatMoney(
      opportunity.expected_profit,
    ),
  );

  setText(
    "riskLevel",
    opportunity.risk_level,
  );

  setText(
    "tradeScore",
    opportunity.trade_score,
  );

  setText(
    "tradeConfidence",
    opportunity.confidence,
  );

  setText(
    "putBuffer",
    formatNumber(opportunity.put_buffer),
  );

  setText(
    "callBuffer",
    formatNumber(opportunity.call_buffer),
  );

  setText(
    "tradeSource",
    opportunity.source,
  );

  setText(
    "liveCredit",
    formatNumber(opportunity.live_credit),
  );

  setText(
    "putCredit",
    formatNumber(opportunity.put_credit),
  );

  setText(
    "callCredit",
    formatNumber(opportunity.call_credit),
  );

  setText(
    "returnOnRisk",
    Number.isFinite(
      Number(opportunity.return_on_risk),
    )
      ? `${formatNumber(
          opportunity.return_on_risk,
          2,
        )}%`
      : "--",
  );

  setText(
    "candidatesEvaluated",
    opportunity.candidates_evaluated,
  );
}


/* =========================================================
   RECOMMENDATION FETCH
========================================================= */

async function fetchRecommendation() {
  try {
    const response = await fetch(
      `${API_URL}?_=${Date.now()}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `API error ${response.status}`,
      );
    }

    const data = await response.json();

    updateDashboard(data);
    setApiStatus(true);
  } catch (error) {
    console.error(
      "Dashboard fetch failed:",
      error,
    );

    setApiStatus(false);

    setText(
      "recommendation",
      "API Offline",
    );
  }
}


/* =========================================================
   BEST TRADE HERO
========================================================= */

function getHeroRecommendation(data, trade) {
  const finalDecision = String(
    trade.final_decision || "",
  ).toUpperCase();

  if (finalDecision) {
    return finalDecision;
  }

  if (
    String(trade.market_regime || "").toUpperCase() ===
    "TRADE"
  ) {
    return "ENTER TRADE";
  }

  if (data.status === "DEMO") {
    return "DEMO";
  }

  return "NO TRADE";
}


function getHeroBadgeClass(
  data,
  recommendation,
) {
  if (data.status === "DEMO") {
    return "demo";
  }

  if (
    recommendation === "ENTER TRADE" ||
    recommendation === "TRADE SMALL"
  ) {
    return "enter";
  }

  return "no-trade";
}


function renderHeroReasons(trade) {
  const reasons =
    Array.isArray(trade.reasons)
      ? trade.reasons
      : [];

  if (reasons.length === 0) {
    return `
      <span>Waiting for trade analysis</span>
    `;
  }

  return reasons
    .map((reason) => {
      const text =
        typeof reason === "string"
          ? reason
          : reason.reason;

      return `<span>✓ ${text}</span>`;
    })
    .join("");
}


async function loadBestTrade() {
  const card = el("bestTradeCard");

  if (!card) {
    return;
  }

  try {
    const response = await fetch(
      `${BEST_TRADE_URL}?_=${Date.now()}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `Best-trade API error ${response.status}`,
      );
    }

    const data = await response.json();
    const trade = data.best_trade;

    if (!trade) {
      card.innerHTML = `
        <div class="hero-header">
          <div>
            <div class="eyebrow">
              Today's Best Trade
            </div>

            <h1>No Trade Available</h1>
          </div>

          <div class="hero-badge no-trade">
            NO TRADE
          </div>
        </div>

        <p>
          ${
            data.reason ||
            "The trade engine did not return a setup."
          }
        </p>
      `;

      return;
    }

    console.log("Best trade:", trade);

    const recommendation =
      getHeroRecommendation(
        data,
        trade,
      );

    const badgeClass =
      getHeroBadgeClass(
        data,
        recommendation,
      );

    const tradeScore = safeNumber(
      trade.trade_quality_score ??
      trade.trade_score,
      0,
    );

    const grade =
      trade.grade || "F";

    const qualityLabel =
      trade.quality_label ||
      `${grade} ${trade.rating || "Poor"}`;

    const pop = safeNumber(
      trade.pop,
      0,
    );

    const reasons =
      renderHeroReasons(trade);

    const touchProbability =
      Number.isFinite(
        Number(trade.probability_of_touch),
      )
        ? `${formatNumber(
            trade.probability_of_touch,
            1,
          )}%`
        : "--";

    card.innerHTML = `
      <div class="hero-header">
        <div>
          <div class="eyebrow">
            Today's Best Trade
          </div>

          <h1>${trade.strategy}</h1>

          <div class="subline">
            SPX ${formatNumber(
              trade.spx_price,
              2,
            )}
            •
            ${trade.dte ?? "--"} DTE
            •
            Expected Move ±${formatNumber(
              trade.expected_move,
              2,
            )}
          </div>
        </div>

        <div class="hero-badge ${badgeClass}">
          ${recommendation}
        </div>
      </div>

      <div class="hero-main">
        <div class="score-block">
          <div class="grade-badge">
            ${grade}
          </div>

          <div class="score-number">
            ${Math.round(tradeScore)}
          </div>

          <div class="score-label">
            ${qualityLabel}
          </div>

          <div class="score-bar">
            <div
              class="score-fill"
              style="width:${Math.min(
                tradeScore,
                100,
              )}%"
            ></div>
          </div>
        </div>

        <div class="legs-grid">
          <div class="option-leg sell">
            <span>SELL</span>
            <strong>
              ${trade.sell_call} CALL
            </strong>
          </div>

          <div class="option-leg buy">
            <span>BUY</span>
            <strong>
              ${trade.buy_call} CALL
            </strong>
          </div>

          <div class="option-leg sell">
            <span>SELL</span>
            <strong>
              ${trade.sell_put} PUT
            </strong>
          </div>

          <div class="option-leg buy">
            <span>BUY</span>
            <strong>
              ${trade.buy_put} PUT
            </strong>
          </div>
        </div>
      </div>

      <div class="why-pills">
        ${reasons}
      </div>

      <div class="metric-strip">
        <div>
          <span>Credit</span>
          <strong>
            ${formatMoney(trade.credit)}
          </strong>
        </div>

        <div>
          <span>Max Profit</span>
          <strong>
            ${formatMoney(trade.max_profit)}
          </strong>
        </div>

        <div>
          <span>Max Risk</span>
          <strong>
            ${formatMoney(trade.max_risk)}
          </strong>
        </div>

        <div>
          <span>POP</span>
          <strong>
            ${formatNumber(pop, 1)}%
          </strong>
        </div>

        <div>
          <span>Risk / Reward</span>
          <strong>
            ${formatNumber(
              trade.risk_reward,
              2,
            )}
          </strong>
        </div>

        <div>
          <span>Touch Probability</span>
          <strong>
            ${touchProbability}
          </strong>
        </div>

        <div>
          <span>Wing</span>
          <strong>
            ${trade.wing_width ?? "--"}
          </strong>
        </div>
      </div>
    `;
  } catch (error) {
    console.error(
      "Best-trade fetch failed:",
      error,
    );

    card.innerHTML = `
      <div class="hero-header">
        <div>
          <div class="eyebrow">
            Today's Best Trade
          </div>

          <h1>Engine Error</h1>
        </div>

        <div class="hero-badge no-trade">
          ERROR
        </div>
      </div>

      <p>
        Could not load the best-trade engine.
      </p>
    `;
  }
}


/* =========================================================
   CLOCK
========================================================= */

function updateClock() {
  setText(
    "clock",
    nowTime(),
  );
}


/* =========================================================
   START DASHBOARD
========================================================= */

fetchRecommendation();
loadBestTrade();
updateClock();

setInterval(
  fetchRecommendation,
  30000,
);

setInterval(
  loadBestTrade,
  60000,
);

setInterval(
  updateClock,
  1000,
);

function updateChecklist(data){

    setCheck(
        "checkVix",
        data.vix_state === "IDEAL"
    );

    setCheck(
        "checkMove",
        data.expected_move_state === "HEALTHY"
    );

    setCheck(
        "checkIV",
        data.iv_rank_state === "GOOD"
    );

    setCheck(
        "checkTrend",
        data.trend !== "UNKNOWN"
    );

    const t = data.opportunity || {};

    setCheck(
        "checkCredit",
        (t.credit || 0) >= 1
    );

    setCheck(
        "checkPOP",
        (t.pop || 0) >= 80
    );

    setCheck(
        "checkTouch",
        (t.touch_probability || 100) <= 35
    );

    setCheck(
        "checkRisk",
        (t.risk_reward || 0) >= 4
    );

}
function setCheck(id, pass){

    const e = el(id);

    if(!e) return;

    e.textContent = pass ? "✅" : "❌";

    e.className = pass ? "pass" : "fail";

}