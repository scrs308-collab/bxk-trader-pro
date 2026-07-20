console.log("BXK Trader Pro Dashboard - V9");

const API_URL = "/api/recommend";
const BEST_TRADE_URL = "/api/best-trade";
const POSITIONS_URL = "/api/position-monitor";
const el = (id) => document.getElementById(id);
let lastSuccessfulUpdate = null;

const STALE_AFTER_MS = 30000;
const OFFLINE_AFTER_MS = 60000;

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

function setApiStatus(status) {

    const apiStatus = el("apiStatus");

    if (!apiStatus) {
        return;
    }

    if (status === "live") {
        apiStatus.textContent = "● LIVE";
        apiStatus.className = "status-pill online";
        return;
    }

    if (status === "stale") {
        apiStatus.textContent = "● STALE";
        apiStatus.className = "status-pill stale";
        return;
    }

    apiStatus.textContent = "● OFFLINE";
    apiStatus.className = "status-pill offline";
}
function updateApiFreshness() {
  if (!lastSuccessfulUpdate) {
    setApiStatus("offline");
    return;
  }

  const age =
    Date.now() - lastSuccessfulUpdate;

  if (age >= OFFLINE_AFTER_MS) {
    setApiStatus("offline");
    return;
  }

  if (age >= STALE_AFTER_MS) {
    setApiStatus("stale");
    return;
  }

  setApiStatus("live");
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
    status.className = "thermo-status";
  }

  const finalDecision = String(
    data.final_decision || "NO TRADE",
  ).toUpperCase();

  const marketPermission = String(
    data.market_permission ||
    data.market_regime ||
    "WAIT",
  ).toUpperCase();

  if (finalDecision === "ENTER TRADE") {
    setText(
      "thermoStatus",
      "TRADE WINDOW OPEN",
    );

    setText(
      "thermoMessage",
      "Market conditions support entry.",
    );

    status?.classList.add("ready");

  } else if (finalDecision === "TRADE SMALL") {
    setText(
      "thermoStatus",
      "TRADE SMALL",
    );

    setText(
      "thermoMessage",
      "Strong setup with one or more market limitations.",
    );

    status?.classList.add("warming");

  } else if (
    marketPermission === "CAUTION" ||
    safeScore >= 75
  ) {
    setText(
      "thermoStatus",
      "CAUTION",
    );

    setText(
      "thermoMessage",
      "Trade quality is acceptable, but conditions do not support full size.",
    );

    status?.classList.add("caution");

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

  } else {
    setText(
      "thermoStatus",
      "WAIT",
    );

    setText(
      "thermoMessage",
      "No approved trade setup.",
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
    data.vix_state || "UNKNOWN",
  ).toUpperCase();

  const expectedMoveState = String(
    data.expected_move_state || "UNKNOWN",
  ).toUpperCase();

  const ivRankState = String(
    data.iv_rank_state || "UNAVAILABLE",
  ).toUpperCase();

  const trend = String(
    data.trend || "UNKNOWN",
  ).toUpperCase();

  const conditions = [
    {
      label:
        vixState === "IDEAL"
          ? "VIX is in the preferred range"
          : `VIX state: ${vixState}`,
      passed: vixState === "IDEAL",
    },
    {
      label:
        expectedMoveState === "HEALTHY"
          ? "Expected move is healthy"
          : expectedMoveState === "LOW"
            ? "Expected move is below the preferred range"
            : `Expected move state: ${expectedMoveState}`,
      passed: expectedMoveState === "HEALTHY",
    },
    {
      label:
        ivRankState === "GOOD"
          ? "IV rank supports premium selling"
          : ivRankState === "UNAVAILABLE"
            ? "IV rank is unavailable and not used"
            : `IV rank state: ${ivRankState}`,
      passed:
        ivRankState === "GOOD" ||
        ivRankState === "UNAVAILABLE",
    },
    {
      label:
        trend !== "UNKNOWN"
          ? `Trend is identified: ${trend}`
          : "Trend is unavailable",
      passed: trend !== "UNKNOWN",
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
  nowTime(),
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

     lastSuccessfulUpdate = Date.now();

     setApiStatus("live");

  } catch (error) {
    console.error(
      "Dashboard fetch failed:",
      error,
    );

    setApiStatus("offline");

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
              Market Decision
            </div>

            <h1>Stand Aside</h1>

            <div class="subline">
                Best candidate found • Not approved for entry
           </div>
          </div>

          <div class="hero-badge no-trade">
            NO TRADE
          </div>
        </div>

        <div class="no-trade-message">
          ${
            data.reason ||
            "The trade engine did not return an approved setup."
          }
        </div>
      `;

      return;
      
        }
        
    const recommendation =
      String(
        trade.final_decision ||
        trade.market_regime ||
        "NO TRADE",
      )
        .trim()
        .toUpperCase();

    const tradeApproved =
      recommendation === "ENTER TRADE" ||
      recommendation === "TRADE" ||
      recommendation === "TRADE SMALL";

    const badgeClass =
      tradeApproved
        ? "enter"
        : "no-trade";

    const badgeText =
      tradeApproved
        ? recommendation
        : "NO TRADE";

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

    const touchProbability =
      Number.isFinite(
        Number(trade.probability_of_touch),
      )
        ? `${formatNumber(
            trade.probability_of_touch,
            1,
          )}%`
        : "--";

    const tradeReasons =
      Array.isArray(trade.reasons)
        ? trade.reasons
        : [];

    const reasons = tradeReasons.length
      ? tradeReasons
          .map((reason) => {
            const text =
              typeof reason === "string"
                ? reason
                : reason.reason ||
                  "Unknown trade condition";

            return `<span>✓ ${text}</span>`;
          })
          .join("")
      : `
          <span>
            No detailed trade reasons returned.
          </span>
        `;

    /*
      NO TRADE / WAIT DISPLAY

      We still show the quality score and candidate
      measurements, but we do not show actionable strikes.
    */

    /*
      APPROVED TRADE DISPLAY

      Full strikes are shown only after BXK approves
      the setup.
    */


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
            ${trade.dte != null ? trade.dte : "--"} DTE
            •
            Expected Move ±${formatNumber(
              trade.expected_move,
              2,
            )}
          </div>
        </div>

        <div class="hero-badge ${badgeClass}">
          ${badgeText}
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
            ${trade.wing_width != null ? trade.wing_width : "--"}
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
   LIVE POSITION MONITOR
========================================================= */

function formatSignedMoney(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  const sign = number > 0 ? "+" : "";

  return `${sign}$${number.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}


function formatSignedNumber(value, decimals = 2) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  const sign = number > 0 ? "+" : "";

  return `${sign}${number.toFixed(decimals)}`;
}


function getPositionStatusClass(pnl) {
  const value = Number(pnl);

  if (!Number.isFinite(value)) {
    return "neutral";
  }

  if (value > 0) {
    return "profit";
  }

  if (value < 0) {
    return "loss";
  }

  return "neutral";
}


function getPositionRecommendation(position) {
  const pnlPercent = Number(
    position.pnl_percent,
  );

  const dte = Number(position.dte);

  if (
    Number.isFinite(pnlPercent) &&
    pnlPercent >= 50
  ) {
    return {
      label: "CONSIDER EXIT",
      className: "profit",
      message:
        "Position has reached at least 50% of maximum profit.",
    };
  }

  if (
    Number.isFinite(pnlPercent) &&
    pnlPercent <= -100
  ) {
    return {
      label: "REVIEW NOW",
      className: "loss",
      message:
        "Loss has reached or exceeded the original credit.",
    };
  }

  if (
    Number.isFinite(dte) &&
    dte <= 0
  ) {
    return {
      label: "EXPIRATION DAY",
      className: "warning",
      message:
        "Position expires today. Monitor short strikes closely.",
    };
  }

  return {
    label: "HOLD",
    className: "neutral",
    message:
      "Position remains open and has not reached an exit threshold.",
  };
}


function renderNoOpenPosition(container, message) {
  container.innerHTML = `
    <div class="position-empty">
      <div class="position-empty-title">
        No Open SPX Position
      </div>

      <div class="position-empty-text">
        ${
          message ||
          "The broker connection returned no active position."
        }
      </div>
    </div>
  `;
}


function renderPositionMonitor(position) {
  const container = el("positionMonitor");

  if (!container) {
    return;
  }

  if (!position) {
    renderNoOpenPosition(container);
    return;
  }

  const pnl = safeNumber(
    position.pnl,
    0,
  );

  const pnlPercent = safeNumber(
    position.pnl_percent,
    0,
  );

  const openingCredit = safeNumber(
    position.opening_credit_dollars,
    0,
  );

  const maxProfit = safeNumber(
    position.max_profit,
    openingCredit,
  );

  const maxRisk = safeNumber(
    position.max_risk,
    0,
  );

  const currentDebit = safeNumber(
    position.current_debit,
    0,
  );

  const quantity = safeNumber(
    position.quantity,
    0,
  );

  const progress =
    maxProfit > 0
      ? Math.max(
          0,
          Math.min(
            100,
            (pnl / maxProfit) * 100,
          ),
        )
      : 0;

  const pnlClass =
    getPositionStatusClass(pnl);

  const recommendation =
    getPositionRecommendation(position);

  const expiration =
    position.expiration || "--";

  const strategy =
    position.strategy ||
    "SPX Iron Condor";

  const putSpread =
    `${position.sell_put ?? "--"} / ${
      position.buy_put ?? "--"
    }`;

  const callSpread =
    `${position.sell_call ?? "--"} / ${
      position.buy_call ?? "--"
    }`;

  const priceSource =
    position.price_source ||
    (
      Array.isArray(position.legs) &&
      position.legs.some(
        (leg) =>
          leg.price_source === "live-mid",
      )
        ? "live-mid"
        : "close-price"
    );

  const sourceLabel =
    priceSource === "live-mid"
      ? "Live midpoint"
      : "Close price fallback";

  const sourceClass =
    priceSource === "live-mid"
      ? "live"
      : "stale";

  const dteLabel =
    Number(position.dte) === 0
      ? "Expires today"
      : `${position.dte ?? "--"} DTE`;

  container.innerHTML = `
    <div class="position-header">
      <div>
        <div class="eyebrow">
          LIVE POSITION
        </div>

        <div class="position-strategy">
          ${strategy}
        </div>

        <div class="position-subline">
          ${quantity} contract${
            quantity === 1 ? "" : "s"
          }
          •
          ${dteLabel}
          •
          Expires ${expiration}
        </div>
      </div>

      <div
        class="position-action ${recommendation.className}"
      >
        ${recommendation.label}
      </div>
    </div>

    <div class="position-summary-grid">
      <div class="position-pnl-box ${pnlClass}">
        <div class="position-label">
          Current P/L
        </div>

        <div class="position-pnl-value">
          ${formatSignedMoney(pnl)}
        </div>

        <div class="position-pnl-percent">
          ${formatSignedNumber(
            pnlPercent,
            1,
          )}%
        </div>

        <div class="position-source ${sourceClass}">
          P/L source: ${sourceLabel}
        </div>
      </div>

      <div class="position-metrics-panel">
        <div class="position-panel-title">
          Broker Values
        </div>

        <div class="position-metric-grid">
          <div>
            <span>Opening Credit</span>
            <strong>
              ${formatMoney(openingCredit)}
            </strong>
          </div>

          <div>
            <span>Current Debit</span>
            <strong>
              ${formatMoney(currentDebit)}
            </strong>
          </div>

          <div>
            <span>Max Profit</span>
            <strong>
              ${formatMoney(maxProfit)}
            </strong>
          </div>

          <div>
            <span>Max Risk</span>
            <strong>
              ${formatMoney(maxRisk)}
            </strong>
          </div>
        </div>
      </div>

      <div class="position-spreads-panel">
        <div class="position-panel-title">
          Position Structure
        </div>

        <div class="spread-card">
          <span>Put Credit Spread</span>
          <strong>${putSpread}</strong>
        </div>

        <div class="spread-card">
          <span>Call Credit Spread</span>
          <strong>${callSpread}</strong>
        </div>

        <div class="position-wing-note">
          Wing width:
          ${position.wing_width ?? "--"} points
        </div>
      </div>
    </div>

    <div class="position-progress-section">
      <div class="position-progress-header">
        <span>Profit Target Progress</span>

        <strong>
          ${formatNumber(
            progress,
            1,
          )}%
        </strong>
      </div>

      <div class="position-progress-bar">
        <div
          class="position-progress-fill ${pnlClass}"
          style="width:${progress}%"
        ></div>
      </div>
    </div>

    <div class="position-coach">
      <div class="position-coach-label">
        BXK POSITION COACH
      </div>

      <div class="position-coach-decision">
        ${recommendation.label}
      </div>

      <div class="position-coach-message">
        ${recommendation.message}
      </div>
    </div>
  `;
}


async function loadPositions() {
  const container = el("positionMonitor");

  if (!container) {
    return;
  }

  try {
    const response = await fetch(
      `${POSITIONS_URL}?_=${Date.now()}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `Positions API error ${response.status}`,
      );
    }

    const data = await response.json();

    const position =
      data.position ||
      (
        Array.isArray(data.positions) &&
        data.positions.length > 0
          ? data.positions[0]
          : null
      );

    if (!position) {
      renderNoOpenPosition(
        container,
        data.message ||
        "No open SPX Iron Condor was found.",
      );

      return;
    }

    renderPositionMonitor(position);
  } catch (error) {
    console.error(
      "Position monitor fetch failed:",
      error,
    );

    container.innerHTML = `
      <div class="position-empty">
        <div class="position-empty-title">
          Position Monitor Offline
        </div>

        <div class="position-empty-text">
          Could not load open positions from the broker connection.
        </div>
      </div>
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
   AUTO-REFRESH CONTROLLER
========================================================= */

const DASHBOARD_REFRESH_MS = 15000;

let dashboardRefreshInProgress = false;
let dashboardRefreshTimer = null;


async function refreshDashboard() {
  if (dashboardRefreshInProgress) {
    return;
  }

  dashboardRefreshInProgress = true;

  try {
    await Promise.allSettled([
      fetchRecommendation(),
      loadBestTrade(),
      loadPositions(),
    ]);
  } finally {
    dashboardRefreshInProgress = false;
  }
}


function startDashboardRefresh() {
  if (dashboardRefreshTimer) {
    clearInterval(dashboardRefreshTimer);
  }

  refreshDashboard();

  dashboardRefreshTimer = setInterval(
    refreshDashboard,
    DASHBOARD_REFRESH_MS,
  );
}


document.addEventListener(
  "visibilitychange",
  () => {
    if (!document.hidden) {
      refreshDashboard();
    }
  },
);


/* =========================================================
   START DASHBOARD
========================================================= */

updateClock();
startDashboardRefresh();

setInterval(
  updateClock,
  1000,
);
setInterval(
  updateApiFreshness,
  1000,
);

function updateChecklist(data) {

    const container =
        document.getElementById(
            "tradeChecklist"
        );

    if (!container) {
        return;
    }

    const score =
        Number(
            data.score ??
            data.trade_score ??
            0
        );

    const strengths =
        Array.isArray(data.strengths)
            ? data.strengths
            : [];

    const weaknesses =
        Array.isArray(data.weaknesses)
            ? data.weaknesses
            : [];

    let html = "";

    strengths.forEach((item) => {

        const reason =
            typeof item === "string"
                ? item
                : item.reason;

        html += `
            <div class="check-item">
                <span style="color:#39d353;">✔</span>
                ${reason}
            </div>
        `;

    });

    weaknesses.forEach((item) => {

        const reason =
            typeof item === "string"
                ? item
                : item.reason;

        html += `
            <div class="check-item">
                <span style="color:#ff5d5d;">✖</span>
                ${reason}
            </div>
        `;

    });

    if (!html) {

        html = `
            <div class="check-item">
                No trade-quality explanation available.
            </div>
        `;

    }

    container.innerHTML = html;

  function updateChecklist(data) {
  const container =
    document.getElementById(
      "tradeChecklist"
    );

  if (!container) {
    return;
  }

  const score = Number(
    data.score ??
    data.trade_score ??
    data.best_trade?.trade_score ??
    0
  );

  const strengths =
    Array.isArray(data.strengths)
      ? data.strengths
      : [];

  const weaknesses =
    Array.isArray(data.weaknesses)
      ? data.weaknesses
      : [];

  const items = [];

  strengths.forEach((item) => {
    const reason =
      typeof item === "string"
        ? item
        : item?.reason;

    if (reason) {
      items.push({
        label: reason,
        passed: true,
      });
    }
  });

  weaknesses.forEach((item) => {
    const reason =
      typeof item === "string"
        ? item
        : item?.reason;

    if (reason) {
      items.push({
        label: reason,
        passed: false,
      });
    }
  });

  const title =
    score > 0
      ? `WHY THIS TRADE SCORES ${Math.round(score)}`
      : "TRADE EVALUATION";

  let html = `
    <div class="checklist-title">
      ${title}
    </div>
  `;

  if (items.length === 0) {
    html += `
      <div class="check-item">
        No trade-quality explanation available.
      </div>
    `;
  } else {
    html += items
      .map(
        (item) => `
          <div class="check-item">
            <span class="${
              item.passed
                ? "pass"
                : "fail"
            }">
              ${item.passed ? "✔" : "✖"}
            </span>

            <span>
              ${item.label}
            </span>
          </div>
        `
      )
      .join("");
  }

  container.innerHTML = html;
}
}