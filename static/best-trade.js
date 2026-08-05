import { BEST_TRADE_URL } from "./config.js";
import {
  el,
  safeNumber,
  formatMoney,
  formatNumber,
} from "./utils.js";

export async function loadBestTrade(
  overrides = {},
) {
  const card = el("bestTradeCard");

  if (!card) {
    return;
  }

  try {
    const strategySelector =
  el("strategySelector");

const dteSelector =
  el("dteSelector");

const wingWidthSelector =
  el("wingWidthSelector");

const contractsSelector =
  el("contractsSelector");

const selectedStrategy =
  overrides.strategy ??
  strategySelector?.value ??
  "auto";

const selectedDte =
  overrides.dte ??
  dteSelector?.value ??
  "1";

const selectedWingWidth =
  overrides.wingWidth ??
  wingWidthSelector?.value ??
  "25";

const selectedContracts =
  overrides.contracts ??
  contractsSelector?.value ??
  "1";

const params = new URLSearchParams({
  strategy: selectedStrategy,
  dte: selectedDte,
  wing_width: selectedWingWidth,
  contracts: selectedContracts,
  _: Date.now().toString(),
});

const response = await fetch(
  `${BEST_TRADE_URL}?${params.toString()}`,
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
          Today's Setup
        </div>

        <h1>Stand Aside</h1>

        <div class="subline">
          No approved setup is currently available.
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
          
          

    const recommendation = String(
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
      tradeApproved ? "enter" : "no-trade";

    const badgeText =
      tradeApproved ? recommendation : "NO TRADE";

        const missionScore = Math.max(
      0,
      Math.min(
        100,
        safeNumber(
          trade.trade_quality_score ??
          trade.trade_score ??
          trade.score ??
          data.score,
          0,
        ),
      ),
    );

    const missionConfidence = String(
      trade.confidence ??
      trade.rating ??
      trade.quality_label ??
      trade.grade ??
      data.confidence ??
     "--",
  ).toUpperCase();
    

    const executionStatus = String(
      data.execution?.status ??
      trade.execution?.status ??
      (
        tradeApproved
          ? "READY"
          : "NOT READY"
      ),
    ).toUpperCase();

    const executionReady =
      data.execution?.ready === true ||
      trade.execution?.ready === true ||
      executionStatus === "READY";

    const missionStatusClass =
      tradeApproved
        ? recommendation === "TRADE SMALL"
          ? "caution"
          : "ready"
        : "stand-down";

    const executionClass =
      executionReady
        ? "ready"
        : "blocked";
    
    const strategyName =
      trade.strategy || "Trade Candidate";

    const spxPrice = safeNumber(
      trade.spx_price,
      0,
    );

    const expectedMove = safeNumber(
      trade.expected_move,
      0,
    );

    const dte =
      trade.dte != null
        ? trade.dte
        : "--";

    const expiration =
      trade.expiration ||
      trade.expiration_date ||
      trade.expires_at ||
      null;

    const expirationText = expiration
      ? new Date(expiration).toLocaleDateString(
          "en-US",
          {
            month: "short",
            day: "numeric",
            year: "numeric",
          },
        )
      : dte === 0
        ? "Today"
        : "--";

    const credit = safeNumber(
      trade.credit ??
      trade.net_credit ??
      trade.opening_credit ??
      trade.premium,
      0,
    );

    const pop = safeNumber(
      trade.pop,
      0,
    );

    const contracts = safeNumber(
  trade.quantity ??
  trade.contracts ??
  data.requested_contracts ??
  selectedContracts,
  1,
);

const maxRisk = safeNumber(
  trade.max_risk ??
  trade.max_loss,
  0,
);

const buyingPowerFromApi = safeNumber(
  trade.buying_power_effect ??
  trade.buying_power ??
  trade.capital_required,
  0,
);

const buyingPower =
  buyingPowerFromApi > 0
    ? buyingPowerFromApi
    : maxRisk;
    
  
    
    const updatedValue =
      trade.timestamp ||
      trade.updated_at ||
      data.timestamp ||
      new Date().toISOString();

    const updatedTime = new Date(
      updatedValue,
    ).toLocaleTimeString(
      "en-US",
      {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
      },
    );

    let legsHtml = "";

    if (
      strategyName === "Bull Put Credit Spread"
)
     {
      legsHtml = `
        <div class="setup-leg">
          <span>SELL PUT</span>
          <strong>
            ${trade.sell_put ?? "--"}
          </strong>
        </div>

        <div class="setup-leg">
          <span>BUY PUT</span>
          <strong>
            ${trade.buy_put ?? "--"}
          </strong>
        </div>
      `;
    } else if (
      strategyName === "Bear Call Credit Spread"
    ) {
      legsHtml = `
        <div class="setup-leg">
          <span>SELL CALL</span>
          <strong>
            ${trade.sell_call ?? "--"}
          </strong>
        </div>

        <div class="setup-leg">
          <span>BUY CALL</span>
          <strong>
            ${trade.buy_call ?? "--"}
          </strong>
        </div>
      `;
    } else {
      legsHtml = `
        <div class="setup-leg">
          <span>SELL CALL</span>
          <strong>
            ${trade.sell_call ?? "--"}
          </strong>
        </div>

        <div class="setup-leg">
          <span>BUY CALL</span>
          <strong>
            ${trade.buy_call ?? "--"}
          </strong>
        </div>

        <div class="setup-leg">
          <span>SELL PUT</span>
          <strong>
            ${trade.sell_put ?? "--"}
          </strong>
        </div>

        <div class="setup-leg">
          <span>BUY PUT</span>
          <strong>
            ${trade.buy_put ?? "--"}
          </strong>
        </div>
      `;
    }

    card.innerHTML = `
    <div class="mission-control">
  <div class="mission-control-heading">
    <div>
      <div class="eyebrow">
        BXK Mission Control
      </div>

      <h1>${strategyName}</h1>

      <div class="subline">
        ${contracts} Contract${
          contracts === 1 ? "" : "s"
        } · ${selectedWingWidth}-Point Wings
      </div>
    </div>

    <div class="mission-status ${missionStatusClass}">
      <span>Mission Status</span>

      <strong>
        ${badgeText}
      </strong>
    </div>
  </div>

  <div class="mission-control-grid">
    <div class="mission-control-item primary">
      <span>Primary Strategy</span>

      <strong>
        ${strategyName}
      </strong>
    </div>

    <div class="mission-control-item">
      <span>Mission Score</span>

      <strong>
        ${Math.round(missionScore)}
      </strong>
    </div>

    <div class="mission-control-item">
      <span>Confidence</span>

      <strong>
        ${missionConfidence}
      </strong>
    </div>

    <div class="mission-control-item ${executionClass}">
      <span>Execution</span>

      <strong>
        ${executionStatus}
      </strong>
    </div>
  </div>
</div>
     

      <div class="setup-market-row">
        <div class="setup-market-item">
          <span>SPX</span>
          <strong>
            ${formatNumber(spxPrice, 2)}
          </strong>
        </div>

        <div class="setup-market-item">
          <span>Expiration</span>
          <strong>
            ${expirationText}
          </strong>
        </div>

        <div class="setup-market-item">
          <span>DTE</span>
          <strong>
            ${dte}
          </strong>
        </div>

        <div class="setup-market-item">
          <span>Expected Move</span>
          <strong>
            ±${formatNumber(
              expectedMove,
              2,
            )}
          </strong>
        </div>
      </div>

      <div class="setup-legs-grid">
        ${legsHtml}
      </div>

      <div class="setup-divider"></div>

      <div class="setup-metrics">
        <div class="setup-metric">
          <span>Credit</span>
          <strong>
            ${formatMoney(credit, 2)}
          </strong>
        </div>

        <div class="setup-metric">
          <span>POP</span>
          <strong>
            ${
              pop > 0
                ? `${formatNumber(pop, 1)}%`
                : "--"
            }
          </strong>
        </div>

        <div class="setup-metric">
          <span>Max Risk</span>
          <strong>
            ${
              maxRisk > 0
                ? formatMoney(maxRisk, 0)
                : "--"
            }
          </strong>
        </div>

        <div class="setup-metric">
          <span>Contracts</span>
          <strong>
            ${contracts}
          </strong>
        </div>

        <div class="setup-metric">
          <span>Buying Power</span>
          <strong>
            ${
              buyingPower > 0
                ? formatMoney(
                    buyingPower,
                    0,
                  )
                : "--"
            }
          </strong>
        </div>
      </div>

      <button
        id="enterTradeButton"
        class="enter-trade-button ${
          tradeApproved
            ? "ready"
            : "disabled"
        }"
        type="button"
        ${tradeApproved ? "" : "disabled"}
        data-trade-approved="${
          tradeApproved
        }"
      >
        ${
          tradeApproved
            ? "ENTER TRADE"
            : "NO TRADE"
        }
      </button>

      <div class="setup-updated">
        Last Updated: ${updatedTime}
      </div>
    `;

        const enterTradeButton = el(
      "enterTradeButton",
    );

    if (
      enterTradeButton &&
      tradeApproved
    ) {
      enterTradeButton.addEventListener(
        "click",
        async () => {
          const originalText =
            enterTradeButton.textContent;

          enterTradeButton.disabled = true;
          enterTradeButton.textContent =
            "BUILDING ORDER...";

          try {
            const previewParams =
              new URLSearchParams({
                strategy: selectedStrategy,
                dte: selectedDte,
                wing_width:
                  selectedWingWidth,
                contracts:
                  selectedContracts,
              });

            const previewResponse =
              await fetch(
                `/api/order-preview?${previewParams.toString()}`,
                {
                  cache: "no-store",
                },
              );

            if (!previewResponse.ok) {
              throw new Error(
                `Order preview error ${previewResponse.status}`,
              );
            }

            const preview =
              await previewResponse.json();

            console.log(
              "BXK order preview:",
              preview,
            );
            
 



const order = preview.order;

if (
  preview.status !== "READY" ||
  !order
) {
  throw new Error(
    preview.message ||
    "Order preview unavailable.",
  );
}

const previewPanel =
  document.createElement("div");

previewPanel.id =
  "orderPreviewPanel";

previewPanel.className =
  "order-preview-panel";

previewPanel.innerHTML = `
  <div class="order-preview-header">
    <div>
      <div class="eyebrow">
        Order Review
      </div>

      <h2>
        ${order.strategy}
      </h2>
    </div>

    <button
      id="closeOrderPreview"
      class="order-preview-close"
      type="button"
    >
      ×
    </button>
  </div>

  <div class="order-preview-grid">
    <div>
      <span>Quantity</span>
      <strong>${order.quantity}</strong>
    </div>

    <div>
      <span>Limit Credit</span>
      <strong>
        ${formatMoney(
          order.limit_price,
          2,
        )}
      </strong>
    </div>

    <div>
      <span>Max Profit</span>
      <strong>
        ${formatMoney(
          order.max_profit,
          0,
        )}
      </strong>
    </div>

    <div>
      <span>Max Risk</span>
      <strong>
        ${formatMoney(
          order.max_risk,
          0,
        )}
      </strong>
    </div>
  </div>

  <div class="order-preview-legs">
    ${order.legs
      .map(
        (leg) => `
          <div class="order-preview-leg">
            <span>
              ${leg.action}
              ${leg.option_type}
            </span>

            <strong>
              ${leg.strike}
            </strong>
          </div>
        `,
      )
      .join("")}
  </div>

  <div class="order-preview-actions">
    <button
      id="cancelOrderPreview"
      class="order-preview-secondary"
      type="button"
    >
      Cancel
    </button>

    <button
      id="confirmOrderPreview"
      class="order-preview-primary"
      type="button"
      disabled
    >
      Confirm Trade
    </button>
  </div>
`;

card.insertAdjacentElement(
  "afterend",
  previewPanel,
);

const closePreview = () => {
  previewPanel.remove();
};

document
  .getElementById(
    "closeOrderPreview",
  )
  ?.addEventListener(
    "click",
    closePreview,
  );

document
  .getElementById(
    "cancelOrderPreview",
  )
  ?.addEventListener(
    "click",
    closePreview,
  );

            enterTradeButton.textContent =
              preview.status === "READY"
                ? "ORDER READY"
                : "NO ORDER AVAILABLE";

          } catch (error) {
            console.error(
              "Order preview failed:",
              error,
            );

            enterTradeButton.textContent =
              "PREVIEW FAILED";

          } finally {
            window.setTimeout(() => {
              enterTradeButton.disabled =
                false;

              enterTradeButton.textContent =
                originalText;
            }, 2000);
          }
        },
      );
    }

  } catch (error) {
    console.error(
      "Error loading best trade:",
      error,
    );

    card.innerHTML = `
      <div class="hero-header">
        <div>
          <div class="eyebrow">
            Today's Setup
          </div>

          <h1>Unable to Load</h1>

          <div class="subline">
            Failed to retrieve the current setup.
          </div>
        </div>

        <div class="hero-badge no-trade">
          ERROR
        </div>
      </div>

      <div class="no-trade-message">
        ${error.message}
      </div>
    `;
  }
}
function closeExistingOrderPreview() {
  document
    .getElementById("orderPreviewPanel")
    ?.remove();
}

function renderOrderPreview({
  card,
  preview,
}) {
  closeExistingOrderPreview();

  const order = preview?.order;

  if (
    preview?.status !== "READY" ||
    !order
  ) {
    throw new Error(
      preview?.message ||
      "Order preview unavailable.",
    );
  }

  const quantity = safeNumber(
    order.quantity,
    1,
  );

  const limitPrice = safeNumber(
    order.limit_price,
    0,
  );

  const maxProfit = safeNumber(
    order.max_profit,
    0,
  );

  const maxRisk = safeNumber(
    order.max_risk,
    0,
  );

  const buyingPower = safeNumber(
    order.buying_power_effect ??
    order.buying_power ??
    maxRisk,
    maxRisk,
  );

  const riskReward =
    maxProfit > 0
      ? maxRisk / maxProfit
      : 0;

  const legs = Array.isArray(order.legs)
    ? order.legs
    : [];

  const previewPanel =
    document.createElement("div");

  previewPanel.id =
    "orderPreviewPanel";

  previewPanel.className =
    "order-preview-panel";

  previewPanel.innerHTML = `
    <div class="order-preview-header">
      <div>
        <div class="eyebrow">
          BXK Order Review
        </div>

        <h2>
          ${order.strategy || "Trade Order"}
        </h2>

        <div class="subline">
          Review every detail before submission.
        </div>
      </div>

      <button
        id="closeOrderPreview"
        class="order-preview-close"
        type="button"
        aria-label="Close order preview"
      >
        ×
      </button>
    </div>

    <div class="order-preview-grid">
      <div>
        <span>Quantity</span>
        <strong>${quantity}</strong>
      </div>

      <div>
        <span>Limit Credit</span>
        <strong>
          ${formatMoney(limitPrice, 2)}
        </strong>
      </div>

      <div>
        <span>Max Profit</span>
        <strong>
          ${formatMoney(maxProfit, 0)}
        </strong>
      </div>

      <div>
        <span>Max Risk</span>
        <strong>
          ${formatMoney(maxRisk, 0)}
        </strong>
      </div>

      <div>
        <span>Buying Power</span>
        <strong>
          ${formatMoney(buyingPower, 0)}
        </strong>
      </div>

      <div>
        <span>Risk / Reward</span>
        <strong>
          ${
            riskReward > 0
              ? `1 : ${formatNumber(
                  riskReward,
                  1,
                )}`
              : "--"
          }
        </strong>
      </div>
    </div>

    <div class="order-preview-legs">
      ${
        legs.length > 0
          ? legs
              .map(
                (leg) => `
                  <div class="order-preview-leg">
                    <span>
                      ${leg.action || "--"}
                      ${leg.option_type || ""}
                    </span>

                    <strong>
                      ${leg.strike ?? "--"}
                    </strong>
                  </div>
                `,
              )
              .join("")
          : `
              <div class="order-preview-empty">
                Order legs unavailable.
              </div>
            `
      }
    </div>

    <div class="order-risk-check">
      <div class="eyebrow">
        Risk Check
      </div>

      <div class="order-risk-row">
        <span>Order preview created</span>
        <strong>PASS</strong>
      </div>

      <div class="order-risk-row">
        <span>Positive credit</span>
        <strong>
          ${limitPrice > 0 ? "PASS" : "FAIL"}
        </strong>
      </div>

      <div class="order-risk-row">
        <span>Defined maximum risk</span>
        <strong>
          ${maxRisk > 0 ? "PASS" : "FAIL"}
        </strong>
      </div>

      <div class="order-risk-row">
        <span>All option legs present</span>
        <strong>
          ${legs.length >= 2 ? "PASS" : "FAIL"}
        </strong>
      </div>
    </div>

    <div class="order-preview-warning">
      Confirm Trade remains disabled until the
      broker submission endpoint and final account
      safeguards are connected.
    </div>

    <div class="order-preview-actions">
      <button
        id="cancelOrderPreview"
        class="order-preview-secondary"
        type="button"
      >
        Cancel
      </button>

      <button
        id="confirmOrderPreview"
        class="order-preview-primary"
        type="button"
        disabled
      >
        Confirm Trade
      </button>
    </div>
  `;

  card.insertAdjacentElement(
    "afterend",
    previewPanel,
  );

  const closePreview = () => {
    previewPanel.remove();
  };

  document
    .getElementById("closeOrderPreview")
    ?.addEventListener(
      "click",
      closePreview,
    );

  document
    .getElementById("cancelOrderPreview")
    ?.addEventListener(
      "click",
      closePreview,
    );
}
export function initializeTradeBuilder() {
  const buildButton =
    el("buildTradeButton");

  if (!buildButton) {
    return;
  }

  buildButton.addEventListener(
    "click",
    async () => {
      const originalText =
        buildButton.textContent;

      buildButton.disabled = true;
      buildButton.textContent =
        "BUILDING...";

      try {
        await loadBestTrade();
      } finally {
        buildButton.disabled = false;
        buildButton.textContent =
          originalText;
      }
    },
  );
}