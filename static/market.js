import {
  el,
  setText,
  safeNumber,
  nowTime,
  formatNumber,
  formatMoney,
  getStatusIcon,
} from "./utils.js";

export function setScore(score) {
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

export function updateDashboard(data, updateChecklist) {
  setText("recommendation", data.recommendation);
  setText(
    "confidence",
    `Confidence: ${data.confidence ?? "--"}`,
  );

  setScore(data.score);
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
  setText("lastUpdate", nowTime());
  updateOpportunityCard(data);
  updateChecklist(data);
}
