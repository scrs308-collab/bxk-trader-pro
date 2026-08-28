import { hasOwnerAccess } from "./access-control.js?v=1";
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
    document.body.dataset.bxkTradeCandidate = "none";

    document.dispatchEvent(
      new CustomEvent("bxk:trade-candidate", {
        detail: { status: "none" },
      }),
    );

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
          
          

    document.body.dataset.bxkTradeCandidate = "ready";

    document.dispatchEvent(
      new CustomEvent("bxk:trade-candidate", {
        detail: {
          status: "ready",
          trade,
        },
      }),
    );

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
      ? new Date(
          `${expiration}T12:00:00`
        ).toLocaleDateString(
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
            
 



            renderOrderPreview({
              preview,
              missionScore,
              missionConfidence,
              executionStatus,
              pop,
              buyingPower,
              strategy: selectedStrategy,
              dte: selectedDte,
              wingWidth: selectedWingWidth,
              contracts: selectedContracts,
            });

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
    .getElementById("orderReviewOverlay")
    ?.remove();

  document
    .getElementById("orderPreviewPanel")
    ?.remove();

  document.body.classList.remove(
    "order-review-open",
  );
}

function renderOrderPreview({
  preview,
  missionScore = 0,
  missionConfidence = "--",
  executionStatus = "--",
  pop = 0,
  buyingPower = 0,
  strategy = "auto",
  dte = 1,
  wingWidth = 25,
  contracts = 1,
}) {
  closeExistingOrderPreview();

  const order = preview?.order;
  const displayedTrade = preview?.trade || {};

  const liveSubmissionEnabled = Boolean(
    preview?.live_submission_enabled,
  );

  const tradingMode = String(
    preview?.trading_mode ||
      (liveSubmissionEnabled ? "LIVE" : "TEST"),
  ).toUpperCase();

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
    displayedTrade.quantity ??
    order.quantity,
    1,
  );

  const limitPrice = safeNumber(
    displayedTrade.credit ??
    displayedTrade.net_credit ??
    displayedTrade.opening_credit ??
    order.limit_price,
    0,
  );

  const maxProfit = safeNumber(
    displayedTrade.max_profit ??
    order.max_profit,
    0,
  );

  const maxRisk = safeNumber(
    displayedTrade.max_risk ??
    displayedTrade.max_loss ??
    order.max_risk,
    0,
  );

  const orderBuyingPower = safeNumber(
    displayedTrade.buying_power_effect ??
    displayedTrade.buying_power ??
    displayedTrade.capital_required ??
    order.buying_power_effect ??
    order.buying_power ??
    buyingPower ??
    maxRisk,
    maxRisk,
  );

  const orderPop = safeNumber(
    displayedTrade.pop ??
    order.pop ??
    pop,
    pop,
  );

  const orderExpiration =
    order.expiration ||
    displayedTrade.expiration ||
    displayedTrade.expiration_date ||
    null;

  const orderDte =
    order.dte ??
    displayedTrade.dte ??
    "--";

  const orderExpirationText = orderExpiration
    ? new Date(
        `${String(orderExpiration).slice(0, 10)}T12:00:00`,
      ).toLocaleDateString(
        "en-US",
        {
          month: "short",
          day: "numeric",
          year: "numeric",
        },
      )
    : Number(orderDte) === 0
      ? "Today"
      : "--";

  const riskReward =
    maxProfit > 0
      ? maxRisk / maxProfit
      : 0;

  const legs = Array.isArray(order.legs)
    ? order.legs
    : [];

  const expectedLegCount =
    String(order.strategy || "")
      .toLowerCase()
      .includes("condor")
      ? 4
      : 2;

  const checks = [
    {
      label: "Order preview created",
      passed: true,
    },
    {
      label: "Positive credit",
      passed: limitPrice > 0,
    },
    {
      label: "Maximum risk defined",
      passed: maxRisk > 0,
    },
    {
      label: "Buying power calculated",
      passed: orderBuyingPower > 0,
    },
    {
      label: "All option legs present",
      passed: legs.length >= expectedLegCount,
    },
    {
      label: "Execution status ready",
      passed:
        String(executionStatus)
          .toUpperCase() === "READY",
    },
  ];

  const allChecksPassed =
    checks.every((check) => check.passed);

  const overlay =
    document.createElement("div");

  overlay.id = "orderReviewOverlay";
  overlay.className = "order-review-overlay";

  overlay.innerHTML = `
    <section
      id="orderPreviewPanel"
      class="order-review-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="orderReviewTitle"
    >
      <header class="order-review-header">
        <div>
          <div class="eyebrow">
            BXK Order Review
          </div>

          <h2 id="orderReviewTitle">
            BXK Trade Review
          </h2>

          <div class="order-review-subtitle">
            ${order.strategy || "Trade Order"}
            &nbsp;&bull;&nbsp;
            ${quantity}
            ${quantity === 1 ? "Contract" : "Contracts"}
          </div>
        </div>

        <button
          id="closeOrderPreview"
          class="order-review-close"
          type="button"
          aria-label="Close order review"
        >
          &times;
        </button>
      </header>

      <div
        class="order-review-mode-banner ${
          liveSubmissionEnabled
            ? "live"
            : "test"
        }"
        role="status"
        aria-live="polite"
      >
        <div>
          <strong>
            BXK ${tradingMode} MODE
          </strong>
          <span>
            ${
              liveSubmissionEnabled
                ? "REAL TASTYTRADE ORDERS ENABLED"
                : "LIVE ORDER SUBMISSION DISABLED"
            }
          </span>
        </div>

        <div class="order-review-mode-state">
          ${
            liveSubmissionEnabled
              ? "LIVE"
              : "SAFE"
          }
        </div>
      </div>

      <div class="order-review-status-row">
        <div>
          <span>Market Score</span>
          <strong>
            ${Math.round(
              safeNumber(missionScore, 0),
            )}
          </strong>
        </div>

        <div>
          <span>Confidence</span>
          <strong>${missionConfidence}</strong>
        </div>

        <div>
          <span>Execution</span>
          <strong class="order-review-execution ${
            String(executionStatus).toUpperCase() === "READY"
              ? "ready"
              : "blocked"
          }">
            ${
              String(executionStatus).toUpperCase() === "READY"
                ? "READY"
                : "BLOCKED"
            }
          </strong>
        </div>

        <div>
          <span>Quantity</span>
          <strong>${quantity}</strong>
        </div>
      </div>

      <div class="order-review-content">
        <div class="order-review-main">
          <section class="order-review-section">
            <div class="order-review-section-heading">
              Option Legs
            </div>

            <div class="order-review-legs">
              ${
                legs.length > 0
                  ? legs
                      .map(
                        (leg) => `
                          <div class="order-review-leg">
                            <span>
                              ${
                                String(
                                  leg.action || "--",
                                ).toUpperCase()
                              }
                              ${
                                String(
                                  leg.option_type || "",
                                ).toUpperCase()
                              }
                            </span>

                            <strong>
                              ${leg.strike ?? "--"}
                            </strong>
                          </div>
                        `,
                      )
                      .join("")
                  : `
                      <div class="order-review-empty">
                        No option legs returned.
                      </div>
                    `
              }
            </div>
          </section>

          <section class="order-review-section">
            <div class="order-review-section-heading">
              Trade Economics
            </div>

            <div class="order-review-metrics">
              <div>
                <span>Expiration</span>
                <strong>
                  ${orderExpirationText}
                </strong>
              </div>

              <div>
                <span>DTE</span>
                <strong>
                  ${orderDte}
                </strong>
              </div>

              <div>
                <span>Limit Credit</span>
                <strong>
                  ${formatMoney(limitPrice, 2)}
                </strong>
              </div>

              <div>
                <span>Probability of Profit</span>
                <strong>
                  ${
                    orderPop > 0
                      ? `${formatNumber(
                          orderPop,
                          1,
                        )}%`
                      : "--"
                  }
                </strong>
              </div>

              <div>
                <span>Maximum Profit</span>
                <strong>
                  ${formatMoney(maxProfit, 0)}
                </strong>
              </div>

              <div>
                <span>Maximum Risk</span>
                <strong>
                  ${formatMoney(maxRisk, 0)}
                </strong>
              </div>

              <div>
                <span>Buying Power</span>
                <strong>
                  ${formatMoney(
                    orderBuyingPower,
                    0,
                  )}
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
          </section>
        </div>

        <aside class="order-review-checks">
          <div class="order-review-section-heading">
            Final Risk Check
          </div>

          ${
            checks
              .map(
                (check) => `
                  <div class="order-review-check ${
                    check.passed
                      ? "passed"
                      : "failed"
                  }">
                    <span class="order-review-check-icon">
                      ${check.passed ? "OK" : "X"}
                    </span>

                    <span>${check.label}</span>

                    <strong>
                      ${check.passed ? "PASS" : "FAIL"}
                    </strong>
                  </div>
                `,
              )
              .join("")
          }

          <div class="order-review-decision ${
            allChecksPassed
              ? "approved"
              : "blocked"
          }">
            <span>Order Status</span>

            <strong>
              ${
                allChecksPassed
                  ? "BXK CHECKS PASSED"
                  : "BLOCKED"
              }
            </strong>
          </div>
        </aside>
      </div>

      <section class="order-review-readiness">
        <div class="order-review-section-heading">
          Broker Readiness
        </div>

        <div class="order-review-readiness-grid">
          <div class="ready">
            <span>OK</span>
            <div>
              <strong>Order Preview</strong>
              <small>Complete</small>
            </div>
          </div>

          <div class="ready">
            <span>OK</span>
            <div>
              <strong>Risk Controls</strong>
              <small>Passed</small>
            </div>
          </div>

          <div
            id="brokerAccountReadiness"
            class="pending"
          >
            <span>--</span>
            <div>
              <strong>Broker Preflight</strong>
              <small>Checking broker...</small>
            </div>
          </div>

          <div
            id="brokerSubmissionReadiness"
            class="pending"
          >
            <span>--</span>
            <div>
              <strong>Live Submission</strong>
              <small>
                ${
                  liveSubmissionEnabled
                    ? "REAL ORDERS ENABLED"
                    : "Protected by BXK master switch"
                }
              </small>
            </div>
          </div>
        </div>

        <div
          id="brokerRiskAudit"
          class="order-review-risk-audit pending"
          aria-live="polite"
        >
          <div>
            <span>BXK Risk</span>
            <strong id="brokerAuditBxkRisk">
              --
            </strong>
          </div>

          <div>
            <span>Broker Impact</span>
            <strong id="brokerAuditImpact">
              --
            </strong>
          </div>

          <div>
            <span>Fees</span>
            <strong id="brokerAuditFees">
              --
            </strong>
          </div>

          <div>
            <span>Variance</span>
            <strong id="brokerAuditVariance">
              --
            </strong>
          </div>
        </div>

        <div
          id="orderBrokerMessage"
          class="order-review-empty"
        >
          Running Tastytrade broker preflight...
        </div>
      </section>

      <footer class="order-review-actions">
        <button
          id="cancelOrderPreview"
          class="order-review-button secondary"
          type="button"
        >
          Cancel
        </button>

        <button
          id="confirmOrderPreview"
          class="order-review-button primary"
          type="button"
          disabled
        >
          CHECKING BROKER...
        </button>
      </footer>
    </section>
  `;

  document.body.appendChild(overlay);

  document.body.classList.add(
    "order-review-open",
  );

  const closeModal = () => {
    closeExistingOrderPreview();
  };

  overlay.addEventListener(
    "click",
    (event) => {
      if (event.target === overlay) {
        closeModal();
      }
    },
  );

  overlay
    .querySelector("#closeOrderPreview")
    ?.addEventListener(
      "click",
      closeModal,
    );

  overlay
    .querySelector("#cancelOrderPreview")
    ?.addEventListener(
      "click",
      closeModal,
    );

  const escapeHandler = (event) => {
    if (event.key === "Escape") {
      closeModal();

      document.removeEventListener(
        "keydown",
        escapeHandler,
      );
    }
  };

  document.addEventListener(
    "keydown",
    escapeHandler,
  );

  const confirmButton = overlay.querySelector(
    "#confirmOrderPreview",
  );

  const accountReadiness = overlay.querySelector(
    "#brokerAccountReadiness",
  );

  const submissionReadiness = overlay.querySelector(
    "#brokerSubmissionReadiness",
  );

  const brokerMessage = overlay.querySelector(
    "#orderBrokerMessage",
  );

  const brokerRiskAudit = overlay.querySelector(
    "#brokerRiskAudit",
  );

  const brokerAuditBxkRisk = overlay.querySelector(
    "#brokerAuditBxkRisk",
  );

  const brokerAuditImpact = overlay.querySelector(
    "#brokerAuditImpact",
  );

  const brokerAuditFees = overlay.querySelector(
    "#brokerAuditFees",
  );

  const brokerAuditVariance = overlay.querySelector(
    "#brokerAuditVariance",
  );

  const reviewId = String(
    preview?.review_id || "",
  ).trim();

  const executionParams = new URLSearchParams({
    strategy,
    dte,
    wing_width: wingWidth,
    contracts,
  });

  if (reviewId) {
    executionParams.set(
      "review_id",
      reviewId,
    );
  }

  const updateReadinessCard = (
    element,
    {
      state = "pending",
      icon = "--",
      detail = "",
    } = {},
  ) => {
    if (!element) {
      return;
    }

    element.classList.remove(
      "ready",
      "pending",
    );

    element.classList.add(state);

    const iconElement =
      element.querySelector("span");

    const detailElement =
      element.querySelector("small");

    if (iconElement) {
      iconElement.textContent = icon;
    }

    if (detailElement) {
      detailElement.textContent = detail;
    }
  };

  const setBrokerMessage = (message) => {
    if (brokerMessage) {
      brokerMessage.textContent = message;
    }
  };

  const setBrokerRiskAudit = ({
    state = "pending",
    bxkRisk = null,
    brokerImpact = null,
    fees = null,
    variance = null,
  } = {}) => {
    if (brokerRiskAudit) {
      brokerRiskAudit.classList.remove(
        "ready",
        "pending",
        "failed",
      );

      brokerRiskAudit.classList.add(state);
    }

    const formatAuditMoney = (value) => {
      if (
        value === null ||
        value === undefined ||
        value === "" ||
        !Number.isFinite(Number(value))
      ) {
        return "--";
      }

      return formatMoney(
        Number(value),
        2,
      );
    };

    if (brokerAuditBxkRisk) {
      brokerAuditBxkRisk.textContent =
        formatAuditMoney(bxkRisk);
    }

    if (brokerAuditImpact) {
      brokerAuditImpact.textContent =
        formatAuditMoney(brokerImpact);
    }

    if (brokerAuditFees) {
      brokerAuditFees.textContent =
        formatAuditMoney(fees);
    }

    if (brokerAuditVariance) {
      brokerAuditVariance.textContent =
        formatAuditMoney(variance);
    }
  };

  const runBrokerPreflight = async () => {
    if (!allChecksPassed) {
      updateReadinessCard(
        accountReadiness,
        {
          state: "pending",
          icon: "X",
          detail: "Local risk check failed",
        },
      );

      updateReadinessCard(
        submissionReadiness,
        {
          state: "pending",
          icon: "X",
          detail: "Submission blocked",
        },
      );

      setBrokerRiskAudit({
        state: "failed",
      });

      setBrokerMessage(
        "BXK local risk checks must pass before broker preflight.",
      );

      if (confirmButton) {
        confirmButton.disabled = true;
        confirmButton.textContent =
          "ORDER BLOCKED";
      }

      return;
    }

    try {
      const response = await fetch(
        `/api/order-dry-run?${executionParams.toString()}`,
        {
          method: "POST",
          cache: "no-store",
        },
      );

      if (!response.ok) {
        throw new Error(
          `Broker preflight error ${response.status}`,
        );
      }

      const result = await response.json();

      console.log(
        "BXK broker preflight:",
        result,
      );

      if (
        result?.status ===
        "BROKER_PREFLIGHT_PASSED"
      ) {
        updateReadinessCard(
          accountReadiness,
          {
            state: "ready",
            icon: "OK",
            detail:
              result.account
                ? `Verified ${result.account}`
                : "Verified",
          },
        );

        const fees = safeNumber(
          result?.broker_preflight?.fees,
          0,
        );

        const brokerBuyingPower =
          result?.broker_preflight?.buying_power || {};

        const reconciliationCheck =
          (result?.broker_checks || []).find(
            (check) =>
              check?.name ===
              "broker_buying_power_matches_bxk",
          );

        setBrokerRiskAudit({
          state:
            reconciliationCheck?.passed
              ? "ready"
              : "failed",
          bxkRisk:
            brokerBuyingPower.bxk_expected,
          brokerImpact:
            brokerBuyingPower.impact,
          fees,
          variance:
            brokerBuyingPower.variance,
        });

        if (!liveSubmissionEnabled) {
          updateReadinessCard(
            submissionReadiness,
            {
              state: "pending",
              icon: "LOCK",
              detail: "BXK master switch is OFF",
            },
          );

          setBrokerMessage(
            fees > 0
              ? `BROKER VERIFIED. Estimated fees: ${formatMoney(
                  fees,
                  2,
                )}. Live trading is disabled.`
              : "BROKER VERIFIED. Live trading is disabled.",
          );

          if (confirmButton) {
            confirmButton.disabled = true;
            confirmButton.textContent =
              "LIVE TRADING OFF";
          }

          return;
        }

        updateReadinessCard(
          submissionReadiness,
          {
            state: "ready",
            icon: "OK",
            detail:
              "REVIEW READY - confirm to submit",
          },
        );

        setBrokerMessage(
          fees > 0
            ? `REVIEW READY. Tastytrade preflight passed. Estimated fees: ${formatMoney(
                fees,
                2,
              )}.`
            : "REVIEW READY. Tastytrade preflight passed.",
        );

        if (confirmButton) {
          confirmButton.disabled = false;
          confirmButton.textContent =
            "SUBMIT LIVE ORDER";
        }

        return;
      }

      const brokerPreflight =
        result?.broker_preflight || {};

      const brokerChecks =
        result?.broker_checks || [];

      const brokerBuyingPower =
        brokerPreflight?.buying_power || {};

      const fees = safeNumber(
        brokerPreflight?.fees,
        0,
      );

      const failedBrokerChecks =
        brokerChecks.filter(
          (check) => check?.passed === false,
        );

      const reserveCheck =
        failedBrokerChecks.find(
          (check) =>
            check?.name ===
            "broker_buying_power_reserve",
        );

      const nonReserveFailures =
        failedBrokerChecks.filter(
          (check) =>
            check?.name !==
            "broker_buying_power_reserve",
        );

      const reconciliationCheck =
        brokerChecks.find(
          (check) =>
            check?.name ===
            "broker_buying_power_matches_bxk",
        );

      const sessionAdvisory =
        (result?.checks || []).find(
          (check) =>
            check?.name === "execution_session" &&
            check?.advisory,
        );

      const brokerVerified =
        Boolean(brokerPreflight) &&
        nonReserveFailures.length === 0;

      setBrokerRiskAudit({
        state:
          reconciliationCheck?.passed
            ? "ready"
            : "failed",
        bxkRisk:
          brokerBuyingPower.bxk_expected,
        brokerImpact:
          brokerBuyingPower.impact,
        fees,
        variance:
          brokerBuyingPower.variance,
      });

      if (
        brokerVerified &&
        reserveCheck
      ) {
        updateReadinessCard(
          accountReadiness,
          {
            state: "ready",
            icon: "OK",
            detail:
              result.account
                ? `Tastytrade verified ${result.account}`
                : "Tastytrade verified",
          },
        );

        updateReadinessCard(
          submissionReadiness,
          {
            state: "pending",
            icon: "X",
            detail: "BXK capital reserve blocked",
          },
        );

        const advisoryText =
          sessionAdvisory
            ? " GTH advisory active."
            : "";

        setBrokerMessage(
          `TASTYTRADE VERIFIED.${advisoryText} ` +
          reserveCheck.message,
        );

        if (confirmButton) {
          confirmButton.disabled = true;
          confirmButton.textContent =
            "RISK BLOCKED";
        }

        return;
      }

      const errorMessage =
        result?.errors?.[0] ||
        result?.message ||
        "Tastytrade broker preflight did not pass.";

      updateReadinessCard(
        accountReadiness,
        {
          state: "pending",
          icon: "X",
          detail: "Broker preflight blocked",
        },
      );

      updateReadinessCard(
        submissionReadiness,
        {
          state: "pending",
          icon: "X",
          detail: "Submission blocked",
        },
      );

      setBrokerMessage(errorMessage);

      if (confirmButton) {
        confirmButton.disabled = true;
        confirmButton.textContent =
          "BROKER BLOCKED";
      }
    } catch (error) {
      console.error(
        "BXK broker preflight failed:",
        error,
      );

      updateReadinessCard(
        accountReadiness,
        {
          state: "pending",
          icon: "X",
          detail: "Broker check failed",
        },
      );

      updateReadinessCard(
        submissionReadiness,
        {
          state: "pending",
          icon: "X",
          detail: "Submission blocked",
        },
      );

      setBrokerMessage(
        "Unable to complete Tastytrade broker preflight.",
      );

      if (confirmButton) {
        confirmButton.disabled = true;
        confirmButton.textContent =
          "PREFLIGHT FAILED";
      }
    }
  };

  const reconcileSubmittedOrder = async (
    orderId,
    initialReconciliation,
  ) => {
    let reconciliation = initialReconciliation;

    for (let attempt = 0; attempt < 5; attempt += 1) {
      if (reconciliation?.status === "RECONCILED") {
        const status =
          reconciliation.broker_status || "Verified";
        const fillQuantity =
          reconciliation.filled_quantity;
        const fillPrice =
          reconciliation.average_fill_price;
        const fillDetail = [
          fillQuantity
            ? `${fillQuantity} filled`
            : null,
          fillPrice
            ? `at ${formatMoney(fillPrice, 2)}`
            : null,
        ].filter(Boolean).join(" ");

        updateReadinessCard(
          submissionReadiness,
          {
            state: "ready",
            icon: "OK",
            detail: fillDetail
              ? `${status} - ${fillDetail}`
              : `${status} - Order ${orderId}`,
          },
        );

        setBrokerMessage(
          fillDetail
            ? `Tastytrade independently verified order ${orderId}: ${status}, ${fillDetail}.`
            : `Tastytrade independently verified order ${orderId}: ${status}.`,
        );

        confirmButton.textContent =
          status.toUpperCase() === "FILLED"
            ? "ORDER FILLED"
            : "ORDER VERIFIED";
        return;
      }

      if (attempt > 0 || !reconciliation) {
        await new Promise((resolve) => {
          window.setTimeout(resolve, 1500);
        });
      }

      try {
        const response = await fetch(
          `/api/order-status?order_id=${encodeURIComponent(orderId)}`,
          {
            cache: "no-store",
          },
        );

        if (response.ok) {
          reconciliation = await response.json();
        }
      } catch (error) {
        console.warn(
          "BXK order reconciliation pending:",
          error,
        );
      }
    }

    updateReadinessCard(
      submissionReadiness,
      {
        state: "pending",
        icon: "...",
        detail: `Order ${orderId} sent - verify broker`,
      },
    );
    setBrokerMessage(
      `Order ${orderId} was accepted, but independent status verification is still pending. Check Tastytrade before taking another action.`,
    );
    confirmButton.textContent = "VERIFY ORDER STATUS";
  };

  confirmButton?.addEventListener(
    "click",
    async () => {
      const liveConfirmed = window.confirm(
        [
          "SUBMIT REAL ORDER TO TASTYTRADE?",
          "",
          `${quantity} ${
            quantity === 1
              ? "contract"
              : "contracts"
          }`,
          `${order.strategy || "BXK trade"}`,
          `Limit credit: ${formatMoney(
            limitPrice,
            2,
          )}`,
          `Maximum risk: ${formatMoney(
            maxRisk,
            0,
          )}`,
          "",
          "This uses REAL MONEY.",
        ].join("\n"),
      );

      if (!liveConfirmed) {
        setBrokerMessage(
          "Live order submission canceled. No order was sent.",
        );

        confirmButton.disabled = false;
        confirmButton.textContent =
          "SUBMIT LIVE ORDER";

        return;
      }

      confirmButton.disabled = true;
      confirmButton.textContent =
        "SUBMITTING...";

      setBrokerMessage(
        "Revalidating BXK order before submission...",
      );

      const submitParams = new URLSearchParams(
        executionParams,
      );

      submitParams.set(
        "confirm_live",
        "true",
      );

      try {
        const response = await fetch(
          `/api/order-submit?${submitParams.toString()}`,
          {
            method: "POST",
            cache: "no-store",
          },
        );

        if (!response.ok) {
          throw new Error(
            `Order submission error ${response.status}`,
          );
        }

        const result = await response.json();

        console.log(
          "BXK order submission:",
          result,
        );

        if (
          result?.status ===
          "LIVE_TRADING_DISABLED"
        ) {
          updateReadinessCard(
            submissionReadiness,
            {
              state: "pending",
              icon: "LOCK",
              detail: "BXK master switch is OFF",
            },
          );

          setBrokerMessage(
            "Broker preflight passed, but BXK live trading is disabled.",
          );

          confirmButton.textContent =
            "LIVE TRADING OFF";

          return;
        }

        if (
          result?.status ===
          "SUBMISSION_UNCONFIRMED"
        ) {
          updateReadinessCard(
            submissionReadiness,
            {
              state: "failed",
              icon: "!",
              detail:
                "VERIFY TASTYTRADE - DO NOT RETRY",
            },
          );

          setBrokerMessage(
            result.message ||
            "Submission could not be confirmed. Verify Tastytrade before taking any action.",
          );

          confirmButton.disabled = true;
          confirmButton.textContent =
            "VERIFY TASTYTRADE";

          return;
        }
        if (result?.status === "SUBMITTED") {
          updateReadinessCard(
            submissionReadiness,
            {
              state: "ready",
              icon: "OK",
              detail:
                result.order_id
                  ? `Verifying order ${result.order_id}`
                  : "Submitted",
            },
          );

          setBrokerMessage(
            result.message ||
            "BXK order submitted to Tastytrade.",
          );

          confirmButton.textContent =
            "ORDER SENT - VERIFYING";

          if (result.order_id) {
            await reconcileSubmittedOrder(
              result.order_id,
              result.reconciliation,
            );
          }

          return;
        }

        const errorMessage =
          result?.message ||
          result?.errors?.[0] ||
          "Order submission was blocked.";

        updateReadinessCard(
          submissionReadiness,
          {
            state: "pending",
            icon: "X",
            detail: "Submission blocked",
          },
        );

        setBrokerMessage(errorMessage);

        confirmButton.textContent =
          "ORDER BLOCKED";
      } catch (error) {
        console.error(
          "BXK order submission response was not confirmed:",
          error,
        );

        updateReadinessCard(
          submissionReadiness,
          {
            state: "failed",
            icon: "!",
            detail:
              "VERIFY TASTYTRADE - DO NOT RETRY",
          },
        );

        setBrokerMessage(
          "BXK lost confirmation of the live submission. " +
          "The order MAY have reached Tastytrade. " +
          "Verify the broker account before taking any action. " +
          "DO NOT RETRY.",
        );

        confirmButton.disabled = true;
        confirmButton.textContent =
          "VERIFY TASTYTRADE";
      }
    },
  );

  if (!hasOwnerAccess()) {
    if (confirmButton) {
      confirmButton.disabled = true;
      confirmButton.textContent =
        "OWNER EXECUTION ONLY";
    }

    setBrokerMessage(
      "Informational trade preview only. " +
      "Broker validation and order execution " +
      "are restricted to the OWNER account.",
    );

    overlay
      .querySelector("#closeOrderPreview")
      ?.focus();

    return;
  }

  runBrokerPreflight();

  overlay
    .querySelector("#closeOrderPreview")
    ?.focus();
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
