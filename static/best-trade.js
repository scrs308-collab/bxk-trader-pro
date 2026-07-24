import { BEST_TRADE_URL } from "./config.js";
import {
  el,
  safeNumber,
  formatMoney,
  formatNumber,
} from "./utils.js";

export async function loadBestTrade() {
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

    const tradeScore = safeNumber(
      trade.trade_quality_score ??
      trade.trade_score,
      0,
    );

    const grade = trade.grade || "F";

    const qualityLabel =
      trade.quality_label ||
      `${grade} ${trade.rating || "Poor"}`;

    const pop = safeNumber(trade.pop, 0);

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
                : reason?.reason ||
                  "Unknown trade condition";

            return `<span>✓ ${text}</span>`;
          })
          .join("")
      : `
          <span>
            No detailed trade reasons returned.
          </span>
        `;

    card.innerHTML = `
      <div class="hero-header">
        <div>
          <div class="eyebrow">
            Today's Best Trade
          </div>

          <h1>${trade.strategy || "Trade Candidate"}</h1>

          <div class="subline">
            SPX ${formatNumber(trade.spx_price, 2)}
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
          <div class="grade-badge">${grade}</div>
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
              ${trade.sell_call ?? "--"} CALL
            </strong>
          </div>

          <div class="option-leg buy">
            <span>BUY</span>
            <strong>
              ${trade.buy_call ?? "--"} CALL
            </strong>
          </div>

          <div class="option-leg sell">
            <span>SELL</span>
            <strong>
              ${trade.sell_put ?? "--"} PUT
            </strong>
          </div>

          <div class="option-leg buy">
            <span>BUY</span>
            <strong>
              ${trade.buy_put ?? "--"} PUT
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
          <strong>${formatMoney(trade.credit)}</strong>
        </div>
        <div>
          <span>Max Profit</span>
          <strong>${formatMoney(trade.max_profit)}</strong>
        </div>
        <div>
          <span>Max Risk</span>
          <strong>${formatMoney(trade.max_risk)}</strong>
        </div>
        <div>
          <span>POP</span>
          <strong>${formatNumber(pop, 1)}%</strong>
        </div>
        <div>
          <span>Risk / Reward</span>
          <strong>
            ${formatNumber(trade.risk_reward, 2)}
          </strong>
        </div>
        <div>
          <span>Touch Probability</span>
          <strong>${touchProbability}</strong>
        </div>
        <div>
          <span>Wing</span>
          <strong>
            ${trade.wing_width ?? "--"}
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
