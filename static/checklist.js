import { el } from "./utils.js";

export function updateChecklist(data) {
  const container = el("tradeChecklist");

  if (!container) {
    return;
  }

  const score = Number(
    data.score ??
    data.trade_score ??
    data.best_trade?.trade_score ??
    0,
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
            <span class="${item.passed ? "pass" : "fail"}">
              ${item.passed ? "✔" : "✖"}
            </span>
            <span>${item.label}</span>
          </div>
        `,
      )
      .join("");
  }

  container.innerHTML = html;
}
