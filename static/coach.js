import {
  el,
  setText,
  safeNumber,
} from "./utils.js";

export function updateCoach(data) {
  const bestTrade =
    data.best_trade ?? {};

  const score = safeNumber(
    data.score ??
      data.trade_score ??
      bestTrade.trade_score,
    0,
  );

  const pop = safeNumber(
    data.pop ??
      bestTrade.pop,
    0,
  );

  const credit = safeNumber(
    data.credit ??
      data.target_credit ??
      bestTrade.credit ??
      bestTrade.target_credit,
    0,
  );

  const riskReward = safeNumber(
    data.risk_reward ??
      bestTrade.risk_reward,
    0,
  );

  const recommendationState = String(
    data.recommendation ?? "",
  ).toUpperCase();

  const tradeState = String(
    data.trade ?? "",
  ).toUpperCase();

  let coachCommand = "WAIT";
  let coachExplanation =
    "Current conditions do not justify a new position.";
  let coachSize = "0 lots";
  let coachCredit = "--";
  const coachTakeProfit = "50%";
  const coachStop = "2× credit";
  let coachReasonClass = "warning";

  const coachReasonItems = [];

  if (
    recommendationState.includes("TRADE SMALL") ||
    tradeState.includes("SMALL")
  ) {
    coachCommand = "TRADE SMALL";
    coachExplanation =
      "Conditions are usable, but reduced position size is favored.";
    coachSize = "1 lot";
    coachReasonClass = "warning";
  } else if (
    recommendationState.includes("TRADE ALLOWED") ||
    recommendationState.includes("ENTER TRADE") ||
    (
      tradeState.includes("TRADE") &&
      !tradeState.includes("NO")
    )
  ) {
    coachCommand = "OPEN POSITION";
    coachExplanation =
      "Trade quality meets the current BXK entry standards.";

    coachSize =
      score >= 90
        ? "3 lots"
        : score >= 80
          ? "2 lots"
          : "1 lot";

    coachReasonClass = "neutral";
  }

  if (
    recommendationState.includes("NO TRADE") ||
    recommendationState.includes("WAIT") ||
    tradeState.includes("NO TRADE") ||
    tradeState.includes("WAIT")
  ) {
    coachCommand = "WAIT";
    coachExplanation =
      "Stand aside until the setup improves.";
    coachSize = "0 lots";
    coachReasonClass = "danger";
  }

  if (
    recommendationState.includes("MANAGE") ||
    recommendationState.includes("CLOSE")
  ) {
    coachCommand = "MANAGE POSITION";
    coachExplanation =
      "An open position requires active management.";
    coachSize = "Open trade";
    coachReasonClass = "warning";
  }

  if (credit > 0) {
    coachCredit = `$${credit.toFixed(2)}`;
  }

  if (score >= 90) {
    coachReasonItems.push(
      `Market score is strong at ${Math.round(score)}.`,
    );
  } else if (score > 0) {
    coachReasonItems.push(
      `Market score is ${Math.round(score)} and does not qualify for full size.`,
    );
  }

  if (pop >= 80) {
    coachReasonItems.push(
      `Probability of profit is ${pop.toFixed(1)}%.`,
    );
  } else if (pop > 0) {
    coachReasonItems.push(
      `Probability of profit is below target at ${pop.toFixed(1)}%.`,
    );
  }

  if (riskReward >= 4) {
    coachReasonItems.push(
      `Risk/reward meets the minimum standard at ${riskReward.toFixed(1)}:1.`,
    );
  } else if (riskReward > 0) {
    coachReasonItems.push(
      `Risk/reward is below the BXK minimum at ${riskReward.toFixed(1)}:1.`,
    );
  }

  setText("coachCommand", coachCommand);
  setText("coachExplanation", coachExplanation);
  setText("coachSize", coachSize);
  setText("coachCredit", coachCredit);
  setText("coachTakeProfit", coachTakeProfit);
  setText("coachStop", coachStop);

  const coachReasons = el("coachReasons");

  if (!coachReasons) {
    return;
  }

  coachReasons.innerHTML =
    coachReasonItems.length > 0
      ? coachReasonItems
          .map(
            (reason) => `
              <div class="coach-reason ${coachReasonClass}">
                ${reason}
              </div>
            `,
          )
          .join("")
      : `
          <div class="coach-reason neutral">
            Waiting for complete trade-quality data...
          </div>
        `;
}
