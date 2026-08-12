import { el } from "./utils.js";

function getReadinessStatus(score) {
  if (score >= 90) {
    return {
      label: "READY",
      className: "ready",
    };
  }

  if (score >= 75) {
    return {
      label: "ALMOST READY",
      className: "almost",
    };
  }

  if (score >= 50) {
    return {
      label: "WARMING UP",
      className: "warming",
    };
  }

  if (score >= 25) {
    return {
      label: "CAUTION",
      className: "caution",
    };
  }

  return {
    label: "WAIT",
    className: "wait",
  };
}

function renderNoTradeChecklist() {
  const container = el("tradeChecklist");

  if (!container) {
    return;
  }


  container.innerHTML = `
    <div class="checklist-header">
      <div>
        <div class="checklist-title">
          TRADE EVALUATION
        </div>

        <div class="checklist-summary">
          0 strengths &middot; 0 concerns
        </div>
      </div>

      <div class="checklist-status wait">
        WAIT
      </div>
    </div>

    <div class="checklist-grid">
      <div class="check-item empty">
        No approved trade to score.
        Waiting for a valid setup.
      </div>
    </div>
  `;
}


export function updateChecklist(data) {
  const container = el("tradeChecklist");

  if (!container) {
    return;
  }


  if (
    document.body.dataset.bxkTradeCandidate === "none"
  ) {
    renderNoTradeChecklist();
    return;
  }

  const score = Number(
    data.score ??
      data.trade_score ??
      data.best_trade?.trade_score ??
      0,
  );

  const strengths = Array.isArray(data.strengths)
    ? data.strengths
    : [];

  const weaknesses = Array.isArray(data.weaknesses)
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

  const readiness = getReadinessStatus(score);

  const title =
    score > 0
      ? `WHY THIS TRADE SCORES ${Math.round(score)}`
      : "TRADE EVALUATION";

  let html = `
    <div class="checklist-header">
      <div>
        <div class="checklist-title">
          ${title}
        </div>

        <div class="checklist-summary">
          ${items.filter((item) => item.passed).length}
          strengths ·
          ${items.filter((item) => !item.passed).length}
          concerns
        </div>
      </div>

      <div class="checklist-status ${readiness.className}">
        ${readiness.label}
      </div>
    </div>

    <div class="checklist-grid">
  `;

  if (items.length === 0) {
    html += `
      <div class="check-item empty">
        No trade-quality explanation available.
      </div>
    `;
  } else {
    html += items
      .map(
        (item) => `
          <div class="check-item ${item.passed ? "passed" : "failed"}">
            <span class="check-icon ${item.passed ? "pass" : "fail"}">
              ${item.passed ? "✔" : "✖"}
            </span>

            <span class="check-label">
              ${item.label}
            </span>
          </div>
        `,
      )
      .join("");
  }

  html += `
    </div>
  `;

  container.innerHTML = html;
}

document.addEventListener(
  "bxk:trade-candidate",
  (event) => {
    const detail = event.detail || {};

    if (detail.status === "none") {
      renderNoTradeChecklist();
      return;
    }

    if (
      detail.status === "ready" &&
      detail.trade
    ) {
      updateChecklist(detail.trade);
    }
  },
);
