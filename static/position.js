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
  const legs = Array.isArray(position.legs)
    ? position.legs
    : [];

  const pnl = safeNumber(
    position.pnl,
    0,
  );

  const pnlPercent = safeNumber(
    position.pnl_percent,
    0,
  );

  const quantity = safeNumber(
    position.quantity,
    0,
  );

  const strategy =
    position.strategy ||
    "SPX Position";

  const expiration =
    position.expiration || "--";

  const positionType = String(
    position.position_type ||
    (
      position.sell_put != null &&
      position.buy_put != null &&
      position.sell_call != null &&
      position.buy_call != null
        ? "IRON_CONDOR"
        : "CUSTOM"
    ),
  ).toUpperCase();

  const isIronCondor =
    positionType === "IRON_CONDOR";

  const isVertical =
    positionType === "VERTICAL";

  const isSingle =
    positionType === "SINGLE";

  const legQuoteUnreliable =
    legs.some(
      (leg) =>
        leg.quote_reliable === false,
    );

  const valuationReliable =
    position.valuation_reliable !== false &&
    !legQuoteUnreliable;

  const pnlIsEstimate =
    position.pnl_is_estimate === true ||
    !valuationReliable;

  const pnlLabel =
    pnlIsEstimate
      ? "OPEN P/L ESTIMATE"
      : "OPEN P/L";

  const pnlClass =
    getPositionStatusClass(pnl);

  const recommendation =
    getPositionRecommendation(position);

  const hasMaxProfit =
    position.max_profit !== null &&
    position.max_profit !== undefined &&
    Number.isFinite(
      Number(position.max_profit),
    );

  const hasMaxRisk =
    position.max_risk !== null &&
    position.max_risk !== undefined &&
    Number.isFinite(
      Number(position.max_risk),
    );

  const maxProfit =
    hasMaxProfit
      ? safeNumber(
          position.max_profit,
          0,
        )
      : null;

  const maxRisk =
    hasMaxRisk
      ? safeNumber(
          position.max_risk,
          0,
        )
      : null;

  const progressRaw =
    maxProfit !== null &&
    maxProfit > 0
      ? (
          pnl /
          maxProfit
        ) * 100
      : 0;

  const progress = Math.max(
    0,
    Math.min(
      100,
      progressRaw,
    ),
  );

  const progressDisplay =
    maxProfit !== null &&
    maxProfit > 0
      ? `${progress.toFixed(1)}%`
      : "--";

  const priceSource =
    position.price_source ||
    (
      legs.some(
        (leg) =>
          leg.price_source ===
          "live-mid",
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

  const brokerOrderId = String(
    position.broker_order_id || "",
  ).trim();

  const brokerLinkHtml =
    position.broker_linked === true &&
    brokerOrderId
      ? `
        <div class="position-source live">
          TASTYTRADE ORDER ${brokerOrderId}
        </div>
      `
      : "";

  const unreliableLegs =
    Array.isArray(
      position.unreliable_legs,
    )
      ? position.unreliable_legs
      : legs
          .filter(
            (leg) =>
              leg.quote_reliable ===
              false,
          )
          .map(
            (leg) =>
              `${
                leg.strike ?? "?"
              } ${
                leg.option_type === "P"
                  ? "PUT"
                  : "CALL"
              }`,
          );

  const quoteWarningHtml =
    !valuationReliable
      ? `
        <div class="position-v10-quote-warning">
          <div>
            QUOTE QUALITY WARNING
          </div>

          <div>
            Wide or incomplete option
            quotes detected.
          </div>

          ${
            unreliableLegs.length
              ? `
                <div>
                  Affected:
                  ${unreliableLegs.join(", ")}
                </div>
              `
              : ""
          }

          <div class="position-v10-quote-warning-action">
            Automated P/L exit guidance suspended.
          </div>
        </div>
      `
      : "";

  let structureHtml = "";

  if (isIronCondor) {
    const sellPut =
      position.sell_put ?? "--";

    const buyPut =
      position.buy_put ?? "--";

    const sellCall =
      position.sell_call ?? "--";

    const buyCall =
      position.buy_call ?? "--";

    structureHtml = `
      <div class="position-v10-spread put">

        <div class="position-v10-spread-name">
          PUT SPREAD
        </div>

        <div class="position-v10-leg short-leg">
          <span>SELL</span>
          <strong>
            ${sellPut} PUT
          </strong>
        </div>

        <div class="position-v10-leg long-leg">
          <span>BUY</span>
          <strong>
            ${buyPut} PUT
          </strong>
        </div>

      </div>

      <div class="position-v10-spread call">

        <div class="position-v10-spread-name">
          CALL SPREAD
        </div>

        <div class="position-v10-leg short-leg">
          <span>SELL</span>
          <strong>
            ${sellCall} CALL
          </strong>
        </div>

        <div class="position-v10-leg long-leg">
          <span>BUY</span>
          <strong>
            ${buyCall} CALL
          </strong>
        </div>

      </div>

      <div class="position-v10-wing-width">
        ${
          position.wing_width ??
          "--"
        }-point wings
      </div>
    `;
  } else if (isVertical) {
    const optionType =
      String(
        position.option_type ||
        "",
      ).toUpperCase() === "PUT"
        ? "PUT"
        : "CALL";

    const spreadClass =
      optionType === "PUT"
        ? "put"
        : "call";

    const spreadType =
      String(
        position.spread_type ||
        "",
      ).toUpperCase();

    structureHtml = `
      <div
        class="
          position-v10-spread
          ${spreadClass}
        "
      >

        <div class="position-v10-spread-name">
          ${optionType}
          ${spreadType}
          SPREAD
        </div>

        <div class="position-v10-leg short-leg">
          <span>SELL</span>
          <strong>
            ${
              position.short_strike ??
              "--"
            }
            ${optionType}
          </strong>
        </div>

        <div class="position-v10-leg long-leg">
          <span>BUY</span>
          <strong>
            ${
              position.long_strike ??
              "--"
            }
            ${optionType}
          </strong>
        </div>

      </div>

      <div class="position-v10-wing-width">
        ${
          position.width ?? "--"
        }-point spread
      </div>
    `;
  } else if (isSingle) {
    const optionType =
      String(
        position.option_type ||
        "",
      ).toUpperCase() === "PUT"
        ? "PUT"
        : "CALL";

    const isShort =
      String(
        position.direction ||
        "",
      ).toUpperCase() ===
      "SHORT";

    const action =
      isShort
        ? "SELL"
        : "BUY";

    const legClass =
      isShort
        ? "short-leg"
        : "long-leg";

    const spreadClass =
      optionType === "PUT"
        ? "put"
        : "call";

    structureHtml = `
      <div
        class="
          position-v10-spread
          ${spreadClass}
        "
      >

        <div class="position-v10-spread-name">
          SINGLE ${optionType}
        </div>

        <div
          class="
            position-v10-leg
            ${legClass}
          "
        >
          <span>${action}</span>
          <strong>
            ${
              position.strike ??
              "--"
            }
            ${optionType}
          </strong>
        </div>

      </div>

      <div class="position-v10-wing-width">
        Unhedged option position
      </div>
    `;
  } else {
    structureHtml = legs
      .map((leg) => {
        const optionType =
          leg.option_type === "P"
            ? "PUT"
            : "CALL";

        const isShort =
          String(
            leg.direction || "",
          ).toUpperCase() ===
          "SHORT";

        return `
          <div
            class="
              position-v10-leg
              ${
                isShort
                  ? "short-leg"
                  : "long-leg"
              }
            "
          >
            <span>
              ${
                isShort
                  ? "SELL"
                  : "BUY"
              }
            </span>

            <strong>
              ${leg.strike ?? "--"}
              ${optionType}
            </strong>
          </div>
        `;
      })
      .join("");
  }

  const metricRow = (
    label,
    value,
    className = "",
  ) => `
    <div class="position-v10-metric">
      <span>${label}</span>
      <strong class="${className}">
        ${value}
      </strong>
    </div>
  `;

  let metricsHtml = "";

  if (isIronCondor) {
    const openingCredit =
      safeNumber(
        position.opening_credit_dollars,
        0,
      );

    const currentDebit =
      safeNumber(
        position.current_debit,
        0,
      );

    const openingCreditPerSpread =
      quantity > 0
        ? (
            openingCredit /
            100 /
            quantity
          )
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

    metricsHtml =
      metricRow(
        "Opening Credit",
        formatMoney(
          openingCredit,
        ),
      ) +
      metricRow(
        "Current Debit",
        formatMoney(
          currentDebit,
        ),
      ) +
      metricRow(
        "Max Profit",
        maxProfit !== null
          ? formatMoney(maxProfit)
          : "--",
        "positive-value",
      ) +
      metricRow(
        "Max Risk",
        maxRisk !== null
          ? formatMoney(maxRisk)
          : "--",
        "negative-value",
      ) +
      metricRow(
        "Stop Debit",
        formatMoney(
          stopDebit,
        ),
        "negative-value",
      ) +
      metricRow(
        "Stop P/L",
        formatSignedMoney(
          stopLossAmount,
        ),
        "negative-value",
      ) +
      `
        <div class="position-v10-stop-note">
          Stop based on 2x opening credit
        </div>
      `;
  } else if (isVertical) {
    const spreadType =
      String(
        position.spread_type ||
        "",
      ).toUpperCase();

    const isCredit =
      spreadType === "CREDIT";

    const openingAmount =
      isCredit
        ? safeNumber(
            position.opening_credit_dollars,
            0,
          )
        : safeNumber(
            position.opening_debit_dollars,
            0,
          );

    const currentValue =
      safeNumber(
        position.current_value,
        0,
      );

    metricsHtml =
      metricRow(
        isCredit
          ? "Opening Credit"
          : "Opening Debit",
        formatMoney(
          openingAmount,
        ),
      ) +
      metricRow(
        "Current Spread Value",
        formatMoney(
          currentValue,
        ),
      ) +
      metricRow(
        "Max Profit",
        maxProfit !== null
          ? formatMoney(maxProfit)
          : "--",
        "positive-value",
      ) +
      metricRow(
        "Max Risk",
        maxRisk !== null
          ? formatMoney(maxRisk)
          : "--",
        "negative-value",
      );

    if (isCredit) {
      const openingCreditPerSpread =
        quantity > 0
          ? (
              openingAmount /
              100 /
              quantity
            )
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

      metricsHtml +=
        metricRow(
          "Stop Debit",
          formatMoney(
            stopDebit,
          ),
          "negative-value",
        ) +
        metricRow(
          "Stop P/L",
          formatSignedMoney(
            stopLossAmount,
          ),
          "negative-value",
        ) +
        `
          <div class="position-v10-stop-note">
            Stop based on 2x opening credit
          </div>
        `;
    }
  } else if (isSingle) {
    const isShort =
      String(
        position.direction ||
        "",
      ).toUpperCase() ===
      "SHORT";

    const openingPrice =
      isShort
        ? safeNumber(
            position.opening_credit,
            0,
          )
        : safeNumber(
            position.opening_debit,
            0,
          );

    const openingDollars =
      openingPrice *
      100 *
      quantity;

    const currentValue =
      safeNumber(
        position.current_value,
        0,
      );

    metricsHtml =
      metricRow(
        isShort
          ? "Opening Credit"
          : "Opening Debit",
        formatMoney(
          openingDollars,
        ),
      ) +
      metricRow(
        "Current Option Value",
        formatMoney(
          currentValue,
        ),
      ) +
      metricRow(
        "Max Profit",
        maxProfit !== null
          ? formatMoney(maxProfit)
          : (
              isShort
                ? "PREMIUM RECEIVED"
                : "--"
            ),
        "positive-value",
      ) +
      metricRow(
        "Max Risk",
        maxRisk !== null
          ? formatMoney(maxRisk)
          : "UNCAPPED",
        "negative-value",
      );
  } else {
    metricsHtml =
      metricRow(
        "Open P/L",
        formatSignedMoney(pnl),
        pnlClass,
      );
  }

  return `
    <div
      class="
        position-monitor-card
        position-v10-card
      "
    >

      <div class="position-v10-header">
        <div>
          <div class="position-v10-strategy">
            ${strategy}
          </div>

          <div class="position-v10-contracts">
            ${quantity}
            contract${
              quantity === 1
                ? ""
                : "s"
            }
          </div>
        </div>

        <div class="position-v10-expiration">
          <strong>
            ${dteLabel}
          </strong>

          <span>
            Expires ${expiration}
          </span>
        </div>
      </div>

      ${quoteWarningHtml}

      <div class="position-v10-summary">

        <div
          class="
            position-v10-pnl
            ${pnlClass}
          "
        >
          <div class="position-v10-label">
            ${pnlLabel}
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
            <span>
              PROFIT CAPTURED
            </span>

            <strong>
              ${progressDisplay}
            </strong>
          </div>

          <div class="position-progress-bar">
            <div
              class="
                position-progress-fill
                ${pnlClass}
              "
              style="
                width:${progress}%
              "
            ></div>
          </div>

          <div class="position-v10-progress-targets">
            <span>0%</span>
            <span>50%</span>
            <span>75%</span>
            <span>100%</span>
          </div>
        </div>

        <div
          class="
            position-source
            ${sourceClass}
          "
        >
          ${sourceLabel}
        </div>

        ${brokerLinkHtml}

      </div>

      <div class="position-v10-body">

        <div class="position-v10-strikes">

          <div class="position-v10-panel-title">
            POSITION STRUCTURE
          </div>

          ${structureHtml}

        </div>

        <div class="position-v10-metrics">

          <div class="position-v10-panel-title">
            TRADE VALUES
          </div>

          ${metricsHtml}

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
          <span>
            BXK POSITION COACH
          </span>

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

  const hasUnreliableValuation =
    positions.some(
      (position) =>
        position?.valuation_reliable === false,
    );

  const totalPnlLabel =
    hasUnreliableValuation
      ? "Total P/L Estimate"
      : "Total Open P/L";

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
          ${totalPnlLabel}
        </div>

        ${
          hasUnreliableValuation
            ? `
              <div class="position-total-estimate-note">
                QUOTE QUALITY WARNING
              </div>
            `
            : ""
        }

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

function renderBrokerConnectionForm(
  container,
  message = "Connect your Tastytrade account to use Position Monitor.",
) {
  container.innerHTML = `
    <div class="position-empty">
      <div class="position-empty-title">
        Connect Tastytrade
      </div>

      <div class="position-empty-text">
        ${message}
      </div>

      <div style="max-width:520px;margin:18px auto;display:grid;gap:12px;text-align:left;">
        <label>
          Client Secret
          <input
            id="brokerClientSecret"
            type="password"
            autocomplete="off"
            style="width:100%;box-sizing:border-box;padding:10px;"
          >
        </label>

        <label>
          Refresh Token
          <input
            id="brokerRefreshToken"
            type="password"
            autocomplete="off"
            style="width:100%;box-sizing:border-box;padding:10px;"
          >
        </label>

        <button
          id="verifyBrokerButton"
          type="button"
        >
          VERIFY TASTYTRADE
        </button>

        <label
          id="brokerAccountWrap"
          hidden
        >
          Account
          <select
            id="brokerAccountNumber"
            style="width:100%;box-sizing:border-box;padding:10px;"
          ></select>
        </label>

        <button
          id="connectBrokerButton"
          type="button"
          hidden
        >
          CONNECT ACCOUNT
        </button>

        <div
          id="brokerConnectionMessage"
          class="position-empty-text"
        ></div>
      </div>
    </div>
  `;

  const secret =
    document.getElementById(
      "brokerClientSecret",
    );

  const token =
    document.getElementById(
      "brokerRefreshToken",
    );

  const verify =
    document.getElementById(
      "verifyBrokerButton",
    );

  const connect =
    document.getElementById(
      "connectBrokerButton",
    );

  const accountWrap =
    document.getElementById(
      "brokerAccountWrap",
    );

  const account =
    document.getElementById(
      "brokerAccountNumber",
    );

  const status =
    document.getElementById(
      "brokerConnectionMessage",
    );

  const setStatus = (value) => {
    if (status) {
      status.textContent = value || "";
    }
  };

  verify?.addEventListener(
    "click",
    async () => {
      const clientSecret =
        secret?.value?.trim() || "";

      const refreshToken =
        token?.value?.trim() || "";

      if (!clientSecret || !refreshToken) {
        setStatus(
          "Enter both credentials first.",
        );
        return;
      }

      verify.disabled = true;

      setStatus(
        "Verifying Tastytrade...",
      );

      try {
        const response = await fetch(
          "/api/broker-connection/verify",
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              client_secret:
                clientSecret,
              refresh_token:
                refreshToken,
            }),
          },
        );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
            "Tastytrade verification failed.",
          );
        }

        const accounts =
          Array.isArray(data.accounts)
            ? data.accounts
            : [];

        if (!accounts.length) {
          throw new Error(
            "No Tastytrade accounts were returned.",
          );
        }

        account.innerHTML = "";

        accounts.forEach(
          (item) => {
            const option =
              document.createElement(
                "option",
              );

            option.value =
              item.account_number;

            option.textContent =
              item.nickname
                ? `${item.nickname} (${item.account_number})`
                : item.account_number;

            account.appendChild(
              option,
            );
          },
        );

        accountWrap.hidden = false;
        connect.hidden = false;

        setStatus(
          "Verified. Select your account and connect.",
        );

      } catch (error) {
        setStatus(
          error.message ||
          "Verification failed.",
        );

      } finally {
        verify.disabled = false;
      }
    },
  );

  connect?.addEventListener(
    "click",
    async () => {
      const clientSecret =
        secret?.value?.trim() || "";

      const refreshToken =
        token?.value?.trim() || "";

      const accountNumber =
        account?.value?.trim() || "";

      if (
        !clientSecret ||
        !refreshToken ||
        !accountNumber
      ) {
        setStatus(
          "Verify credentials and select an account.",
        );
        return;
      }

      connect.disabled = true;

      setStatus(
        "Connecting account...",
      );

      try {
        const response = await fetch(
          "/api/broker-connection/connect",
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              client_secret:
                clientSecret,
              refresh_token:
                refreshToken,
              account_number:
                accountNumber,
            }),
          },
        );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
            "Unable to connect account.",
          );
        }

        secret.value = "";
        token.value = "";

        setStatus(
          "Connected. Loading positions...",
        );

        await loadPositions();

      } catch (error) {
        connect.disabled = false;

        setStatus(
          error.message ||
          "Unable to connect account.",
        );
      }
    },
  );
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
      if (response.status === 409) {
        let detail =
          "Connect your Tastytrade account to use Position Monitor.";

        try {
          const errorData =
            await response.json();

          detail =
            errorData.detail || detail;
        } catch {
          // Keep default message.
        }

        renderBrokerConnectionForm(
          container,
          detail,
        );

        return;
      }

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
