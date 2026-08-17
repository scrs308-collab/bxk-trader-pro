import {
  el,
  setText,
  safeNumber,
  nowTime,
  formatNumber,
  formatMoney,
  getStatusIcon,
} from "./utils.js";
import { updateCoach } from "./coach.js";

export function setScore(score) {
  const safeScore = Math.max(
    0,
    Math.min(100, safeNumber(score)),
  );

  setText("score", Math.round(safeScore));

  let grade = "F";

  if (safeScore >= 95) {
    grade = "A+";
  } else if (safeScore >= 90) {
    grade = "A";
  } else if (safeScore >= 85) {
    grade = "A-";
  } else if (safeScore >= 80) {
    grade = "B+";
  } else if (safeScore >= 75) {
    grade = "B";
  } else if (safeScore >= 70) {
    grade = "B-";
  } else if (safeScore >= 65) {
    grade = "C+";
  } else if (safeScore >= 60) {
    grade = "C";
  } else if (safeScore >= 50) {
    grade = "D";
  }

  setText("scoreGrade", `Grade ${grade}`);

  const scoreFill = el("scoreFill");

  if (scoreFill) {
    scoreFill.style.width = `${safeScore}%`;
  }
}

export function renderReasons(reasons) {
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
        : reason?.reason || "Unknown reason";

    list.appendChild(li);
  });
}

export function renderMarketBlockers(data) {
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

function getMarketStatus(data = {}) {
  return String(
    data.condor_stability?.market_status ??
    data.market_status ??
    data.snapshot?.market_status ??
    "UNKNOWN",
  ).toUpperCase();
}


function isMarketLive(data = {}) {
  return getMarketStatus(data) === "LIVE";
}


export function updateThermometer(score, data = {}) {
  const safeScore = Math.max(
    0,
    Math.min(100, safeNumber(score)),
  );

  setText("thermoValue", `${Math.round(safeScore)}%`);

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

  if (!isMarketLive(data)) {
    setText("thermoStatus", "MARKET CLOSED");
    setText(
      "thermoMessage",
      "New trade entry is disabled outside regular market hours.",
    );
    status?.classList.add("wait");
    renderMarketBlockers(data);
    return;
  }

  if (finalDecision === "ENTER TRADE") {
    setText("thermoStatus", "TRADE WINDOW OPEN");
    setText(
      "thermoMessage",
      "Market conditions support entry.",
    );
    status?.classList.add("ready");
  } else if (finalDecision === "TRADE SMALL") {
    setText("thermoStatus", "TRADE SMALL");
    setText(
      "thermoMessage",
      "Strong setup with one or more market limitations.",
    );
    status?.classList.add("warming");
  } else if (
    marketPermission === "CAUTION" ||
    safeScore >= 75
  ) {
    setText("thermoStatus", "CAUTION");
    setText(
      "thermoMessage",
      "Trade quality is acceptable, but conditions do not support full size.",
    );
    status?.classList.add("caution");
  } else if (safeScore >= 50) {
    setText("thermoStatus", "WARMING UP");
    setText(
      "thermoMessage",
      "Market conditions are improving.",
    );
    status?.classList.add("warming");
  } else {
    setText("thermoStatus", "WAIT");
    setText(
      "thermoMessage",
      "No approved trade setup.",
    );
    status?.classList.add("wait");
  }

  renderMarketBlockers(data);
}

export function updateOpportunityCard(data) {
  const opportunity = data.opportunity || {};

  setText("strategyName", opportunity.strategy);
  setText("spxPrice", formatNumber(opportunity.spx_price));
  setText(
    "expectedMovePoints",
    formatNumber(opportunity.expected_move),
  );
  setText("sellPut", opportunity.sell_put);
  setText("buyPut", opportunity.buy_put);
  setText("sellCall", opportunity.sell_call);
  setText("buyCall", opportunity.buy_call);
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
  setText("maxRisk", formatMoney(opportunity.max_risk));
  setText(
    "expectedProfit",
    formatMoney(opportunity.expected_profit),
  );
  setText("riskLevel", opportunity.risk_level);
  setText("tradeScore", opportunity.trade_score);
  setText("tradeConfidence", opportunity.confidence);
  setText("putBuffer", formatNumber(opportunity.put_buffer));
  setText("callBuffer", formatNumber(opportunity.call_buffer));
  setText("tradeSource", opportunity.source);
  setText("liveCredit", formatNumber(opportunity.live_credit));
  setText("putCredit", formatNumber(opportunity.put_credit));
  setText("callCredit", formatNumber(opportunity.call_credit));
  setText(
    "returnOnRisk",
    Number.isFinite(Number(opportunity.return_on_risk))
      ? `${formatNumber(opportunity.return_on_risk, 2)}%`
      : "--",
  );
  setText(
    "candidatesEvaluated",
    opportunity.candidates_evaluated,
  );
}

function renderMarketSummary(data) {
  const container = el("marketSummary");

  if (!container) {
    return;
  }

  const opportunity = data.opportunity || {};

  const spx =
    opportunity.spx_price ??
    data.spx ??
    data.snapshot?.price;

  const expectedMove =
    opportunity.expected_move ??
    data.expected_move ??
    data.snapshot?.expected_move;

  const vix =
    data.vix ??
    data.snapshot?.vix;

  const vix1d =
    data.vix1d ??
    data.snapshot?.vix1d;

  const trend = String(
    data.trend || "UNKNOWN",
  ).toUpperCase();

  const vixState = String(
    data.vix_state || "UNKNOWN",
  ).toUpperCase();

  const expectedMoveState = String(
    data.expected_move_state || "UNKNOWN",
  ).toUpperCase();

  const stability =
    data.condor_stability ??
    data.snapshot?.condor_stability ??
    {};

  const stabilityAvailable =
    stability.available === true;

  const stabilitySignalReady =
    stability.signal_ready === true;

  const stabilityState = String(
    stability.state || "UNAVAILABLE",
  ).toUpperCase();

  const stabilityReason = String(
    stability.reason_code || "",
  ).toUpperCase();

  const expansionPressure =
    stability.range_expansion_pressure ?? {};

  const sessionPhase = String(
    stability.session_phase ||
    expansionPressure.session_phase ||
    "CLOSED",
  ).toUpperCase();

  const minutesSinceOpen =
    stability.minutes_since_open ??
    expansionPressure.minutes_since_open;

  const pressureAvailable =
    expansionPressure.available === true;

  let stabilityMessage =
    "Waiting for Condor Stability data.";

  if (!stabilityAvailable) {
    stabilityMessage =
      "Stability data unavailable.";
  } else if (
    stabilityReason === "MARKET_NOT_LIVE"
  ) {
    stabilityMessage =
      "Market closed - signal disabled.";
  } else if (
    stabilityReason === "VIX1D_UNAVAILABLE"
  ) {
    stabilityMessage =
      "VIX1D unavailable - signal disabled.";
  } else if (stabilitySignalReady) {
    stabilityMessage =
      "Live inputs available - observing thresholds.";
  } else {
    stabilityMessage =
      "Observation only - signal not ready.";
  }

  const riskProfile =
    data.condor_risk_profile ??
    data.snapshot?.condor_risk_profile ??
    {};

  const riskStatus = String(
    riskProfile.status ||
    "INSUFFICIENT_HISTORY",
  ).toUpperCase();

  const riskSampleDays = safeNumber(
    riskProfile.sample_days,
  );

  const rangeRisk =
    riskProfile.range_expansion ?? {};

  const forwardRisk =
    riskProfile.forward_risk ?? {};

  const forward0945 =
    forwardRisk["0945"] ?? {};

  const forward1000 =
    forwardRisk["1000"] ?? {};

  const forward1030 =
    forwardRisk["1030"] ?? {};

  let riskStatusLabel = "LEARNING";

  if (riskStatus === "AVAILABLE") {
    riskStatusLabel = "HISTORY READY";
  } else if (riskStatus === "OBSERVING") {
    riskStatusLabel = "BUILDING HISTORY";
  }

  const rawMarketPermission = String(
    data.market_permission ||
    data.market_regime ||
    data.trade ||
    "WAIT",
  ).toUpperCase();

  const marketPermission =
    isMarketLive(data)
      ? rawMarketPermission
      : "MARKET CLOSED";

  const recommendation =
    isMarketLive(data)
      ? (
          data.recommendation ||
          "No recommendation available."
        )
      : "New trade entry is disabled outside regular market hours.";

  const score = Math.max(
    0,
    Math.min(100, safeNumber(data.score))
  );

  container.innerHTML = `
    <div class="market-summary-grid">
      <div class="market-summary-metric">
        <span>SPX</span>
        <strong>${formatNumber(spx)}</strong>
      </div>

      <div class="market-summary-metric">
        <span>VIX</span>
        <strong id="marketSummaryVix">${formatNumber(vix)}</strong>
      </div>

      <div class="market-summary-metric">
        <span>VIX1D</span>
        <strong id="marketSummaryVix1d">${formatNumber(vix1d)}</strong>
      </div>

      <div class="market-summary-metric">
        <span>Expected Move</span>
        <strong>±${formatNumber(expectedMove)} pts</strong>
      </div>

      <div class="market-summary-metric">
        <span>Trend</span>
        <strong>${trend}</strong>
      </div>

      <div class="market-summary-metric">
        <span>VIX State</span>
        <strong>${vixState}</strong>
      </div>

      <div class="market-summary-metric">
        <span>Expected Move State</span>
        <strong>${expectedMoveState}</strong>
      </div>

      <div class="market-summary-metric">
        <span>Market Score</span>
        <strong>${Math.round(score)} / 100</strong>
      </div>
    </div>

    <div class="market-summary-outlook">
      <div class="card-label">
        Condor Stability
      </div>

      <div class="market-summary-permission">
        <span
          style="
            color: #94a3b8;
            font-weight: 800;
          "
        >
          &#9679; ${stabilityState}
        </span>
      </div>

      <div class="market-summary-recommendation">
        ${stabilityMessage}
      </div>

      <div
        class="market-summary-grid"
        style="margin-top: 14px;"
      >
        <div class="market-summary-metric">
          <span>Implied Move</span>
          <strong>
            &plusmn;${formatNumber(
              stability.implied_move
            )} pts
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>Directional Used</span>
          <strong>
            ${formatNumber(
              stability.directional_consumed_pct,
              1
            )}%
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>Range Used</span>
          <strong>
            ${formatNumber(
              stability.range_band_consumed_pct,
              1
            )}%
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>Directional Excursion</span>
          <strong>
            ${formatNumber(
              stability.max_directional_excursion,
              1
            )} pts
          </strong>
        </div>
      </div>

      <div
        class="market-summary-grid"
        style="margin-top: 14px;"
      >
        <div class="market-summary-metric">
          <span>Session Phase</span>
          <strong>${sessionPhase}</strong>
        </div>

        <div class="market-summary-metric">
          <span>Minutes Since Open</span>
          <strong>
            ${
              minutesSinceOpen != null
                ? Math.round(minutesSinceOpen)
                : "--"
            }
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>Expected Pace</span>
          <strong>
            ${
              pressureAvailable
                ? `${formatNumber(
                    expansionPressure.expected_pace_pct,
                    1
                  )}%`
                : "--"
            }
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>Expansion Pressure</span>
          <strong>
            ${
              pressureAvailable
                ? `${formatNumber(
                    expansionPressure.pressure_ratio,
                    2
                  )}x`
                : "--"
            }
          </strong>
        </div>
      </div>
    </div>

    <div class="market-summary-outlook">
      <div class="card-label">
        Historical Range Risk
      </div>

      <div class="market-summary-permission">
        <span
          style="
            color: #94a3b8;
            font-weight: 800;
          "
        >
          &#9679; ${riskStatusLabel}
        </span>
      </div>

      <div class="market-summary-recommendation">
        ${Math.round(riskSampleDays)} completed trading
        ${Math.round(riskSampleDays) === 1 ? "day" : "days"}
        in the current risk sample.
      </div>

      <div
        class="market-summary-grid"
        style="margin-top: 14px;"
      >
        <div class="market-summary-metric">
          <span>Implied Move</span>
          <strong>
            &plusmn;${formatNumber(
              riskProfile.current_implied_move ??
              stability.implied_move,
              1
            )} pts
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>Normal Stress</span>
          <strong>
            ${
              rangeRisk.normal_stress_move != null
                ? `&plusmn;${formatNumber(
                    rangeRisk.normal_stress_move,
                    1
                  )} pts`
                : "--"
            }
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>High Stress</span>
          <strong>
            ${
              rangeRisk.high_stress_move != null
                ? `&plusmn;${formatNumber(
                    rangeRisk.high_stress_move,
                    1
                  )} pts`
                : "--"
            }
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>Recent Extreme</span>
          <strong>
            ${
              rangeRisk.recent_extreme_move != null
                ? `&plusmn;${formatNumber(
                    rangeRisk.recent_extreme_move,
                    1
                  )} pts`
                : "--"
            }
          </strong>
        </div>
      </div>

      <div
        class="market-summary-grid"
        style="margin-top: 14px;"
      >
        <div class="market-summary-metric">
          <span>09:45 90% Forward</span>
          <strong>
            ${
              forward0945.p90_forward_move != null
                ? `${formatNumber(
                    forward0945.p90_forward_move,
                    1
                  )} pts`
                : "LEARNING"
            }
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>10:00 90% Forward</span>
          <strong>
            ${
              forward1000.p90_forward_move != null
                ? `${formatNumber(
                    forward1000.p90_forward_move,
                    1
                  )} pts`
                : "LEARNING"
            }
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>10:30 90% Forward</span>
          <strong>
            ${
              forward1030.p90_forward_move != null
                ? `${formatNumber(
                    forward1030.p90_forward_move,
                    1
                  )} pts`
                : "LEARNING"
            }
          </strong>
        </div>

        <div class="market-summary-metric">
          <span>History Status</span>
          <strong>${riskStatus}</strong>
        </div>
      </div>
    </div>

    <div class="market-summary-outlook">
      <div class="card-label">
        Current Trade Outlook
      </div>

      <div class="market-summary-permission">
        ${marketPermission}
      </div>

      <div class="market-summary-recommendation">
        ${recommendation}
      </div>
    </div>
  `;
}
export function updateMarketSummaryLiveData(data = {}) {
  const vix = Number(data.vix);
  const vix1d = Number(data.vix1d);
  const spx = Number(data.spx);

  const account =
    data.account ||
    data.account_balance ||
    data.balances ||
    {};

  const optionalNumber = (value) => {
    if (
      value === null ||
      value === undefined ||
      value === ""
    ) {
      return null;
    }

    const parsed = Number(value);

    return Number.isFinite(parsed)
      ? parsed
      : null;
  };

  const netLiquidation = optionalNumber(
    account.net_liquidation ??
      account.net_liquidating_value,
  );

  const buyingPower = optionalNumber(
    account.buying_power ??
      account.equity_buying_power,
  );

  const derivativePower = optionalNumber(
    account.derivative_buying_power ??
      account.derivative_buying_power_effect,
  );

  const openPositions = optionalNumber(
    account.open_positions ??
      data.open_positions,
  );

  const accountNumber = String(
    account.number ||
    account.account_number ||
    data.account_number ||
    "",
  );

  const maskedAccount =
    accountNumber.length > 4
      ? `••••${accountNumber.slice(-4)}`
      : accountNumber || "Unavailable";

  const brokerConnectionKnown =
    typeof data.connected === "boolean" ||
    typeof account.connected === "boolean" ||
    accountNumber.length > 0;

  const brokerConnected =
    data.connected === true ||
    account.connected === true ||
    accountNumber.length > 0;

  const spxAvailable =
    Number.isFinite(spx) && spx > 0;

  const vixAvailable =
    Number.isFinite(vix) && vix > 0;

  const vix1dAvailable =
    Number.isFinite(vix1d) && vix1d > 0;

  const marketDataHealthy =
    spxAvailable &&
    vixAvailable &&
    vix1dAvailable;

  setText(
    "marketSummaryVix",
    vixAvailable
      ? formatNumber(vix, 2)
      : "Unavailable",
  );

  setText(
    "marketSummaryVix1d",
    vix1dAvailable
      ? formatNumber(vix1d, 2)
      : "Unavailable",
  );

  setText(
    "systemSpxStatus",
    spxAvailable
      ? `${formatNumber(spx, 2)} · LIVE`
      : "Unavailable",
  );

  setText(
    "systemVix1dStatus",
    vix1dAvailable
      ? `${formatNumber(vix1d, 2)} · LIVE`
      : "Unavailable",
  );

  setText(
    "systemAccount",
    maskedAccount,
  );

  setText(
    "systemNetLiq",
    netLiquidation !== null
      ? `$${netLiquidation.toLocaleString(
          "en-US",
          {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          },
        )}`
      : "--",
  );

  setText(
    "systemBuyingPower",
    buyingPower !== null
      ? `$${buyingPower.toLocaleString(
          "en-US",
          {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          },
        )}`
      : "--",
  );

  setText(
    "systemDerivativePower",
    derivativePower !== null
      ? `$${derivativePower.toLocaleString(
          "en-US",
          {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          },
        )}`
      : "--",
  );

  setText(
    "systemOpenPositions",
    openPositions !== null
      ? String(openPositions)
      : "--",
  );

  setText(
    "systemMarketStatus",
    data.market_status ||
      data.snapshot?.market_status ||
      "Unavailable",
  );

  setText(
    "systemServerTime",
    data.server_time ||
      data.timestamp ||
      data.snapshot?.timestamp ||
      "--",
  );

  setText(
    "systemLastUpdate",
    nowTime(),
  );

  const brokerStatus = el(
    "systemBrokerStatus",
  );

  if (brokerStatus) {
    if (!brokerConnectionKnown) {
      brokerStatus.textContent = "NOT CHECKED";
      brokerStatus.className =
        "system-value pending";
    } else {
      brokerStatus.textContent =
        brokerConnected
          ? "CONNECTED"
          : "OFFLINE";

      brokerStatus.className =
        brokerConnected
          ? "system-value operational"
          : "system-value offline";
    }
  }

  const marketDataStatus = el(
    "systemMarketDataStatus",
  );

  if (marketDataStatus) {
    marketDataStatus.textContent =
      marketDataHealthy
        ? "LIVE"
        : "DEGRADED";

    marketDataStatus.className =
      marketDataHealthy
        ? "system-value operational"
        : "system-value degraded";
  }

  const spxStatus = el(
    "systemSpxStatus",
  );

  if (spxStatus) {
    spxStatus.className =
      spxAvailable
        ? "system-good"
        : "system-error";
  }

  const vix1dStatus = el(
    "systemVix1dStatus",
  );

  if (vix1dStatus) {
    vix1dStatus.className =
      vix1dAvailable
        ? "system-good"
        : "system-warning";
  }
}

function renderStrategyPlaybook(data) {
  const container = el("strategyPlaybook");

  if (!container) {
    return;
  }

  const backendStrategies = Array.isArray(
    data.strategies,
  )
    ? data.strategies
    : [];

  const finalDecision = String(
    data.final_decision || "NO TRADE",
  ).toUpperCase();

  const strategyDetails = {
    "Iron Condor": {
      description:
        "Primary BXK strategy for a range-bound market with healthy premium.",
      conditions:
        "Mixed or neutral trend · Ideal VIX · Healthy expected move",
      risk: "Defined",
    },

    "Credit Spread": {
      description:
        "Directional premium-selling strategy for a clearly bullish or bearish market.",
      conditions:
        "Confirmed direction · Healthy premium · Strong market score",
      risk: "Defined",
    },

    "Iron Butterfly": {
      description:
        "Higher-credit strategy when SPX is expected to remain near a central price.",
      conditions:
        "Range-bound market · High confidence · Strong premium",
      risk: "Defined / Higher",
    },

    "Broken-Wing Butterfly": {
      description:
        "Directional structure with asymmetric wings and controlled risk.",
      conditions:
        "Directional bias · Favorable pricing · Strong setup",
      risk: "Defined",
    },
  };
  
  const strategies = backendStrategies.map(
    (strategy) => {
      const name = String(
        strategy.name || "Unknown Strategy",
      );

      const details =
        strategyDetails[name] || {
          description:
            strategy.reason ||
            "Strategy evaluated by the BXK recommendation engine.",
          conditions:
            strategy.reason ||
            "See current market analysis.",
          risk: "Defined",
        };

      const strategyScore = Math.max(
        0,
        Math.min(
          100,
          safeNumber(strategy.score),
        ),
      );

      return {
        name,
        description: details.description,
        conditions:
          strategy.reason ||
          details.conditions,
        risk: details.risk,
        score: strategyScore,
        confidence:
          strategy.confidence || "--",

        rawScore: safeNumber(
          strategy.raw_score,
          strategyScore,
        ),

        scoreCapped:
          strategy.score_capped === true,

        factors: Array.isArray(
          strategy.factors,
        )
          ? strategy.factors
          : [],

        status: String(
          strategy.status || "DENIED",
        ).toUpperCase(),
      };
    },
  );    
     strategies.push({
  name: "No Trade",
  description:
    "Protect capital when BXK entry requirements are not satisfied.",
  conditions:
    "Weak score · Poor premium · Conflicting market conditions",
  risk: "None",

  score:
    finalDecision === "NO TRADE"
      ? 100
      : 0,

  rawScore:
    finalDecision === "NO TRADE"
      ? 100
      : 0,

  scoreCapped: false,

  confidence:
    finalDecision === "NO TRADE"
      ? "High"
      : "Low",

  status:
    finalDecision === "NO TRADE"
      ? "APPROVED"
      : "DENIED",

  factors: [],
});
   

  container.innerHTML = `
    <div class="strategy-playbook-grid">
      ${strategies
        .map((strategy) => {
          const statusClass =
            strategy.status.toLowerCase();

          return `
            <div class="strategy-playbook-card">
              <div class="strategy-playbook-header">
                <strong>${strategy.name}</strong>

                <span class="strategy-status ${statusClass}">
                  ${strategy.status}
                </span>
              </div>

              <p class="strategy-description">
  ${strategy.description}
</p>

<div class="strategy-protocol-section">
  <div class="strategy-protocol-title">
    Assessment
  </div>

  <div class="strategy-assessment-list">
    ${
      (strategy.factors ?? []).length > 0
        ? (strategy.factors ?? [])
            .map((factor) => {
              const points = safeNumber(
                factor.points,
              );

              return `
  <div class="strategy-assessment-row">

    <span class="assessment-pass">
      ✓
    </span>

    <span class="assessment-label">
      ${factor.label || "Factor"}
    </span>

    <span class="assessment-fill"></span>

    <strong class="assessment-points">
      +${points}
    </strong>

  </div>
`;
                  
            })
            .join("")
        : `
            <div class="strategy-assessment-row">
              <span class="assessment-neutral">
                —
              </span>

              <span class="assessment-label">
                No qualification factors
              </span>
            </div>
          `
    }
  </div>
</div>

<div class="strategy-protocol-section">
  <div class="strategy-protocol-title">
    Decision
  </div>

  <div class="strategy-decision-grid">
    <div class="strategy-decision-item">
      <span>Final Score</span>

      <strong>
        ${strategy.score} / 100
      </strong>
    </div>

    ${
      strategy.scoreCapped
        ? `
            <div class="strategy-decision-item">
              <span>Raw Score</span>

              <strong>
                ${strategy.rawScore}
              </strong>
            </div>
          `
        : ""
    }

    <div class="strategy-decision-item">
      <span>Confidence</span>

      <strong>
        ${strategy.confidence}
      </strong>
    </div>

    <div class="strategy-decision-item">
      <span>Risk</span>

      <strong>
        ${strategy.risk}
      </strong>
    </div>
  </div>
</div>

<div class="strategy-protocol-section">
  <div class="strategy-protocol-title">
    BXK Analysis
  </div>

  <div class="strategy-analysis-text">
    ${strategy.conditions}
  </div>
</div>
            </div>
          `;
        })
        .join("")}
    </div>
     `;
}


function renderSystemDashboard(data) {
  const container = el("systemDashboard");

  if (!container) {
    return;
  }

  const score = Math.max(
    0,
    Math.min(100, safeNumber(data.score))
  );

  const vixState = String(
    data.vix_state || "UNKNOWN"
  ).toUpperCase();

  const expectedMoveState = String(
    data.expected_move_state || "UNKNOWN"
  ).toUpperCase();

  const vixHealthy =
    vixState !== "UNKNOWN" &&
    vixState !== "UNAVAILABLE";

  const expectedMoveHealthy =
    expectedMoveState !== "UNKNOWN" &&
    expectedMoveState !== "UNAVAILABLE";

  container.innerHTML = `
    <div class="system-status-grid">
      <div class="system-status-card">
        <span>System</span>
        <strong class="system-value operational">
          OPERATIONAL
        </strong>
      </div>

      <div class="system-status-card">
        <span>API</span>
        <strong class="system-value operational">
          ONLINE
        </strong>
      </div>

      <div class="system-status-card">
        <span>Broker</span>
        <strong
          id="systemBrokerStatus"
          class="system-value pending"
        >
          CHECKING
        </strong>
      </div>

      <div class="system-status-card">
        <span>Market Data</span>
        <strong
          id="systemMarketDataStatus"
          class="system-value pending"
        >
          CHECKING
        </strong>
      </div>

      <div class="system-status-card">
        <span>Last Update</span>
        <strong id="systemLastUpdate">
          ${nowTime()}
        </strong>
      </div>
    </div>

    <div class="system-section-grid">
      <section class="system-section">
        <div class="system-section-title">
          Market Data Feeds
        </div>

        <div class="system-row">
          <span>SPX Quote</span>
          <strong id="systemSpxStatus">
            Checking...
          </strong>
        </div>

        <div class="system-row">
          <span>VIX Quote</span>
          <strong
            class="${
              vixHealthy
                ? "system-good"
                : "system-warning"
            }"
          >
            ${vixState}
          </strong>
        </div>

        <div class="system-row">
          <span>VIX1D Quote</span>
          <strong
            id="systemVix1dStatus"
            class="system-warning"
          >
            Checking...
          </strong>
        </div>

        <div class="system-row">
          <span>Expected Move</span>
          <strong
            class="${
              expectedMoveHealthy
                ? "system-good"
                : "system-warning"
            }"
          >
            ${expectedMoveState}
          </strong>
        </div>

        <div class="system-row">
          <span>Decision Engine</span>
          <strong class="system-good">
            ${Math.round(score)} / 100
          </strong>
        </div>
      </section>

      <section class="system-section">
        <div class="system-section-title">
          Broker & Account
        </div>

        <div class="system-row">
          <span>Account</span>
          <strong id="systemAccount">
            Checking...
          </strong>
        </div>

        <div class="system-row">
          <span>Net Liquidation</span>
          <strong id="systemNetLiq">--</strong>
        </div>

        <div class="system-row">
          <span>Buying Power</span>
          <strong id="systemBuyingPower">--</strong>
        </div>

        <div class="system-row">
          <span>Derivative Buying Power</span>
          <strong id="systemDerivativePower">--</strong>
        </div>

        <div class="system-row">
          <span>Open Positions</span>
          <strong id="systemOpenPositions">--</strong>
        </div>
      </section>

      <section class="system-section">
        <div class="system-section-title">
          Engine Information
        </div>

        <div class="system-row">
          <span>Application</span>
          <strong>BXK Trader Pro V10</strong>
        </div>

        <div class="system-row">
          <span>Decision Engine</span>
          <strong>Engine V4</strong>
        </div>

        <div class="system-row">
          <span>API Route</span>
          <strong>CANONICAL_V2</strong>
        </div>

        <div class="system-row">
          <span>Market Status</span>
          <strong id="systemMarketStatus">
            Checking...
          </strong>
        </div>

        <div class="system-row">
          <span>Server Time</span>
          <strong id="systemServerTime">--</strong>
        </div>
      </section>

      <section class="system-section">
        <div class="system-section-title">
          Safety Controls
        </div>

        <div class="system-row">
          <span>Maximum Trades</span>
          <strong>1 per day</strong>
        </div>

        <div class="system-row">
          <span>Approved Wings</span>
          <strong>5 / 10 / 20 / 25 points</strong>
        </div>

        <div class="system-row">
          <span>Minimum Credit</span>
          <strong>$1.00</strong>
        </div>

        <div class="system-row">
          <span>Minimum POP</span>
          <strong>80%</strong>
        </div>

        <div class="system-row">
          <span>Maximum Touch</span>
          <strong>35%</strong>
        </div>

        <div class="system-row">
          <span>Stop-Loss Rule</span>
          <strong>2× opening credit</strong>
        </div>

        <div class="system-row">
          <span>Order Execution</span>
          <strong class="system-warning">
            MANUAL ONLY
          </strong>
        </div>
      </section>
    </div>
  `;
}

export function updateDashboard(data, updateChecklist) {
   const tradeState = String(
    data.trade ?? "",
  ).toUpperCase();

  setText("recommendation", data.recommendation);
  setText(
    "confidence",
    `Confidence: ${data.confidence ?? "--"}`,
  );
    const recommendationState = String(
    data.recommendation ?? "",
  ).toUpperCase();

  let recommendationAction =
    "MONITOR MARKET";

  if (!isMarketLive(data)) {
    recommendationAction =
      "MARKET CLOSED";
  } else if (
    recommendationState.includes("TRADE ALLOWED") ||
    recommendationState.includes("ENTER TRADE")
  ) {
    recommendationAction =
      "OPEN POSITION";
  } else if (
    recommendationState.includes("TRADE SMALL") ||
    tradeState.includes("SMALL")
  ) {
    recommendationAction =
      "REDUCE SIZE";
  } else if (
    recommendationState.includes("NO TRADE") ||
    recommendationState.includes("WAIT") ||
    tradeState.includes("NO TRADE") ||
    tradeState.includes("WAIT")
  ) {
    recommendationAction =
      "WAIT FOR BETTER SETUP";
  } else if (
    recommendationState.includes("MANAGE") ||
    recommendationState.includes("CLOSE")
  ) {
    recommendationAction =
      "MANAGE OPEN POSITION";
  }

  setText(
    "recommendationAction",
    recommendationAction,
  );

setScore(data.score);

setText(
  "tradeState",
  isMarketLive(data)
    ? (tradeState || "--")
    : "MARKET CLOSED",
);

updateCoach(data);
updateThermometer(data.score, data);
   
  setText(
    "trade",
    `${getStatusIcon(data.trade)} ${data.trade ?? "--"}`,
  );
  setText(
    "trend",
    `${getStatusIcon(data.trend)} ${data.trend ?? "--"}`,
  );
  setText(
    "vixState",
    `${getStatusIcon(data.vix_state)} ${
      data.vix_state ?? "--"
    }`,
  );
  const expectedMoveValue =
  data.opportunity?.expected_move;

setText(
  "expectedMove",
  expectedMoveValue != null
    ? `±${formatNumber(expectedMoveValue)}`
    : "--",
);
 
      
  setText(
    "ivRank",
    `${getStatusIcon(data.iv_rank_state)} ${
      data.iv_rank_state ?? "--"
    }`,
  );
   

  let regimeDescription =
    "Waiting for market analysis...";

  if (
    tradeState.includes("TRADE") &&
    !tradeState.includes("NO")
  ) {
    regimeDescription =
      "Premium-selling conditions are favorable.";
  } else if (
    tradeState.includes("WAIT") ||
    tradeState.includes("NO TRADE")
  ) {
    regimeDescription =
      "Conditions do not currently justify a new position.";
  } else if (
    tradeState.includes("CAUTION") ||
    tradeState.includes("SMALL")
  ) {
    regimeDescription =
      "Conditions are usable, but reduced size and tighter discipline are favored.";
  }

  
    renderReasons(data.reasons);
    setText("lastUpdate", nowTime());
    updateOpportunityCard(data);
    updateChecklist(data);
    renderMarketSummary(data);
    renderStrategyPlaybook(data);
    renderSystemDashboard(data);
}