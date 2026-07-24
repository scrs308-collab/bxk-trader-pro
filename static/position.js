import { POSITIONS_URL } from "./config.js";
import {
  el,
  safeNumber,
  formatMoney,
  formatSignedMoney,
  formatNumber,
  formatSignedNumber,
} from "./utils.js";

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
  const coach = position?.coach;

  if (
    coach &&
    typeof coach.recommendation === "string" &&
    coach.recommendation.trim()
  ) {
    const label =
      coach.recommendation
        .trim()
        .toUpperCase();

    const riskLevel =
      String(
        coach.risk_level || "",
      ).toUpperCase();

    let className = "neutral";

    if (
      label.includes("CLOSE") ||
      label.includes("EXIT")
    ) {
      className = "profit";
    }

    if (
      riskLevel === "MODERATE" ||
      riskLevel === "HIGH"
    ) {
      className = "warning";
    }

    if (
      riskLevel === "CRITICAL" ||
      label.includes("REVIEW")
    ) {
      className = "loss";
    }

    const messages = Array.isArray(
      coach.messages,
    )
      ? coach.messages.filter(Boolean)
      : [];

    const message =
      coach.headline ||
      messages[0] ||
      "Follow the Position Coach recommendation.";

    return {
      label,
      className,
      message,
    };
  }

  const pnlPercent = Number(
    position.pnl_percent,
  );

  const dte = Number(position.dte);

  if (
    Number.isFinite(pnlPercent) &&
    pnlPercent >= 75
  ) {
    return {
      label: "CLOSE POSITION",
      className: "profit",
      message:
        "Strong profit target achieved. Protect the gain.",
    };
  }

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
    dte <= 0 &&
    Number.isFinite(pnlPercent) &&
    pnlPercent >= 25
  ) {
    return {
      label: "CLOSE POSITION",
      className: "warning",
      message:
        "Expiration-day profit is available. Avoid unnecessary late-day risk.",
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

function renderPositionCard(position) {
  const pnl = safeNumber(position.pnl, 0);

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

  const openingCreditPerSpread =
    quantity > 0
      ? openingCredit / 100 / quantity
      : 0;

  const stopDebit =
    openingCreditPerSpread * 2;

  const stopLossAmount =
    quantity > 0
      ? -(
          (
            stopDebit -
            openingCreditPerSpread
          ) *
          100 *
          quantity
        )
      : 0;

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

  const sellPut =
    position.sell_put ?? "--";

  const buyPut =
    position.buy_put ?? "--";

  const sellCall =
    position.sell_call ?? "--";

  const buyCall =
    position.buy_call ?? "--";

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
      ? "LIVE MIDPOINT"
      : "CLOSE PRICE";

  const sourceClass =
    priceSource === "live-mid"
      ? "live"
      : "stale";

  const dteLabel =
    Number(position.dte) === 0
      ? "EXPIRES TODAY"
      : `${position.dte ?? "--"} DTE`;

  return `
    <div class="position-monitor-card position-v10-card">

      <div class="position-v10-header">
        <div>
          <div class="position-v10-strategy">
            ${strategy}
          </div>

          <div class="position-v10-contracts">
            ${quantity} contract${
              quantity === 1 ? "" : "s"
            }
          </div>
        </div>

        <div class="position-v10-expiration">
          <strong>${dteLabel}</strong>
          <span>Expires ${expiration}</span>
        </div>
      </div>

      <div class="position-v10-summary">

        <div class="position-v10-pnl ${pnlClass}">
          <div class="position-v10-label">
            OPEN P/L
          </div>

          <div class="position-v10-pnl-value">
            ${formatSignedMoney(pnl)}
          </div>

          <div class="position-v10-pnl-percent">
            ${formatSignedNumber(
              pnlPercent,
              1,
            )}%
          </div>
        </div>

        <div class="position-v10-progress">
          <div class="position-v10-progress-header">
            <span>PROFIT CAPTURED</span>

            <strong>
              ${formatNumber(progress, 1)}%
            </strong>
          </div>

          <div class="position-progress-bar">
            <div
              class="position-progress-fill ${pnlClass}"
              style="width:${progress}%"
            ></div>
          </div>

          <div class="position-v10-progress-targets">
            <span>0%</span>
            <span>50%</span>
            <span>75%</span>
            <span>100%</span>
          </div>
        </div>

        <div class="position-source ${sourceClass}">
          ${sourceLabel}
        </div>

      </div>

      <div class="position-v10-body">

        <div class="position-v10-strikes">

          <div class="position-v10-panel-title">
            POSITION STRUCTURE
          </div>

          <div class="position-v10-spread put">

            <div class="position-v10-spread-name">
              PUT SPREAD
            </div>

            <div class="position-v10-leg short-leg">
              <span>SELL</span>
              <strong>${sellPut} PUT</strong>
            </div>

            <div class="position-v10-leg long-leg">
              <span>BUY</span>
              <strong>${buyPut} PUT</strong>
            </div>

          </div>

          <div class="position-v10-spread call">

            <div class="position-v10-spread-name">
              CALL SPREAD
            </div>

            <div class="position-v10-leg short-leg">
              <span>SELL</span>
              <strong>${sellCall} CALL</strong>
            </div>

            <div class="position-v10-leg long-leg">
              <span>BUY</span>
              <strong>${buyCall} CALL</strong>
            </div>

          </div>

          <div class="position-v10-wing-width">
            ${position.wing_width ?? "--"}-point wings
          </div>

        </div>

        <div class="position-v10-metrics">

          <div class="position-v10-panel-title">
            TRADE VALUES
          </div>

          <div class="position-v10-metric">
            <span>Opening Credit</span>
            <strong>
              ${formatMoney(openingCredit)}
            </strong>
          </div>

          <div class="position-v10-metric">
            <span>Current Debit</span>
            <strong>
              ${formatMoney(currentDebit)}
            </strong>
          </div>

          <div class="position-v10-metric">
            <span>Max Profit</span>
            <strong class="positive-value">
              ${formatMoney(maxProfit)}
            </strong>
          </div>

          <div class="position-v10-metric">
            <span>Max Risk</span>
            <strong class="negative-value">
              ${formatMoney(maxRisk)}
            </strong>
          </div>

          <div class="position-v10-metric">
            <span>Stop Debit</span>
            <strong class="negative-value">
              ${formatMoney(stopDebit)}
            </strong>
          </div>

          <div class="position-v10-metric">
            <span>Stop P/L</span>
            <strong class="negative-value">
              ${formatSignedMoney(
                stopLossAmount,
              )}
            </strong>
          </div>

          <div class="position-v10-stop-note">
            Stop based on 2× opening credit
          </div>

        </div>

      </div>

      <div
        class="
          position-coach
          position-v10-coach
          ${recommendation.className}
        "
      >
        <div class="position-v10-coach-heading">
          <span>BXK POSITION COACH</span>

          <strong>
            ${recommendation.label}
          </strong>
        </div>

        <div class="position-coach-message">
          ${recommendation.message}
        </div>
      </div>

    </div>
  `;
}

function renderPositionMonitor(
  positions,
  totalOpenPnl = null,
) {
  const container = el("positionMonitor");

  if (!container) {
    return;
  }

  if (
    !Array.isArray(positions) ||
    positions.length === 0
  ) {
    renderNoOpenPosition(container);
    return;
  }

  const total =
    Number.isFinite(Number(totalOpenPnl))
      ? Number(totalOpenPnl)
      : positions.reduce(
          (sum, position) =>
            sum + safeNumber(position.pnl, 0),
          0,
        );

  const totalClass =
    getPositionStatusClass(total);

  const cards = positions
    .map(renderPositionCard)
    .join("");

  container.innerHTML = `
    <div class="position-summary-bar">
      <div>
        <div class="eyebrow">
          LIVE POSITION MONITOR
        </div>

        <div class="position-strategy-large">
          ${positions.length}
          Open Position${positions.length === 1 ? "" : "s"}
        </div>
      </div>

      <div class="position-total-block ${totalClass}">
        <div class="position-label">
          Total Open P/L
        </div>

        <div class="position-pnl-value-large">
          ${formatSignedMoney(total)}
        </div>
      </div>
    </div>

    <div class="position-card-stack">
      ${cards}
    </div>
  `;
}

export async function loadPositions() {
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

    const positions =
      Array.isArray(data.positions)
        ? data.positions
        : (
            data.position
              ? [data.position]
              : []
          );

    if (positions.length === 0) {
      renderNoOpenPosition(
        container,
        data.message ||
        "No open SPX Iron Condor was found.",
      );
      return;
    }

    renderPositionMonitor(
      positions,
      data.total_open_pnl,
    );
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
