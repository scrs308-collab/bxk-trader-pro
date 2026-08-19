import { initializeAuthUi } from "./auth-ui.js?v=1";
console.log("BXK Trader Pro Dashboard - V10");

import {
  API_URL,
  DASHBOARD_REFRESH_MS,
  STALE_AFTER_MS,
} from "./config.js";

import {
  el,
  setText,
  nowTime,
} from "./utils.js";

import {
  updateDashboard,
  updateMarketSummaryLiveData,
} from "./market.js";

import {
  updateChecklist,
} from "./checklist.js";

import {
  loadBestTrade,
  initializeTradeBuilder,
} from "./best-trade.js?v=12";

import {
  loadPositions,
} from "./position.js";

import {
  initializeSystemSettings,
} from "./system-settings.js?v=1";

let lastSuccessfulUpdate = null;
let consecutiveNetworkFailures = 0;
let backendOffline = false;
let dashboardRefreshInProgress = false;
let dashboardRefreshTimer = null;

const RECENT_CONDOR_RISK_REFRESH_MS =
  5 * 60 * 1000;

let recentCondorRiskCache = {
  status: "NO_DATA",
  count: 0,
  limit: 10,
  summaries: [],
};

let lastRecentCondorRiskFetch = 0;

function setApiStatus(status) {
  const apiStatus = el("apiStatus");

  if (!apiStatus) {
    return;
  }

  if (status === "live") {
    apiStatus.textContent = "\u25CF API LIVE";
    apiStatus.className = "status-pill online";
    return;
  }

  if (status === "stale") {
    apiStatus.textContent = "\u25CF STALE";
    apiStatus.className = "status-pill stale";
    return;
  }

  apiStatus.textContent = "\u25CF OFFLINE";
  apiStatus.className = "status-pill offline";
}

function updateApiFreshness() {
  if (backendOffline) {
    setApiStatus("offline");
    return;
  }

  if (!lastSuccessfulUpdate) {
    setApiStatus("stale");
    return;
  }

  const age =
    Date.now() - lastSuccessfulUpdate;

  if (age >= STALE_AFTER_MS) {
    setApiStatus("stale");
    return;
  }

  setApiStatus("live");
}

async function fetchRecentCondorRisk() {
  const now = Date.now();

  const cacheFresh =
    lastRecentCondorRiskFetch > 0 &&
    (
      now - lastRecentCondorRiskFetch
    ) < RECENT_CONDOR_RISK_REFRESH_MS;

  if (cacheFresh) {
    return recentCondorRiskCache;
  }

  try {
    const response = await fetch(
      `/api/condor-risk-summary/recent?limit=10&_=${now}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `Recent Condor risk error ${response.status}`,
      );
    }

    recentCondorRiskCache =
      await response.json();

    lastRecentCondorRiskFetch = now;
  } catch (error) {
    console.error(
      "Recent Condor risk history failed:",
      error,
    );
  }

  return recentCondorRiskCache;
}


async function fetchRecommendation() {
  try {
    const response = await fetch(
      `${API_URL}?_=${Date.now()}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `API error ${response.status}`,
      );
    }

    const data = await response.json();

    const recentCondorRisk =
      await fetchRecentCondorRisk();

    const dashboardData = {
      ...data,
      recent_condor_risk:
        recentCondorRisk,
    };

    updateDashboard(
      dashboardData,
      updateChecklist,
    );

    lastSuccessfulUpdate = Date.now();
    consecutiveNetworkFailures = 0;
    backendOffline = false;
    setApiStatus("live");
  } catch (error) {
    console.error(
      "Dashboard fetch failed:",
      error,
    );

    const networkFailure =
      error instanceof TypeError;

    if (networkFailure) {
      consecutiveNetworkFailures += 1;
    } else {
      consecutiveNetworkFailures = 0;
    }

    backendOffline =
      networkFailure &&
      consecutiveNetworkFailures >= 3;

    setApiStatus(
      backendOffline ? "offline" : "stale",
    );

    if (backendOffline) {
      setText(
        "recommendation",
        "API Offline",
      );
    }
  }
}

function updateClock() {
  setText("clock", nowTime());
}

let savedSpxTradeControls = null;


function getSelectedUnderlying() {
  const selector =
    document.getElementById(
      "underlyingSelector",
    );

  return String(
    selector?.value || "SPX",
  ).toUpperCase();
}


function setSelectValue(id, value) {
  const control =
    document.getElementById(id);

  if (!control) {
    return;
  }

  control.value = String(value);
}


function setTradeControlsDisabled(disabled) {
  [
    "strategySelector",
    "dteSelector",
    "wingWidthSelector",
    "contractsSelector",
  ].forEach((id) => {
    const control =
      document.getElementById(id);

    if (control) {
      control.disabled = disabled;
    }
  });
}


function applyUnderlyingMode() {
  const underlying =
    getSelectedUnderlying();

  const strategy =
    document.getElementById(
      "strategySelector",
    );

  const dte =
    document.getElementById(
      "dteSelector",
    );

  const wing =
    document.getElementById(
      "wingWidthSelector",
    );

  const contracts =
    document.getElementById(
      "contractsSelector",
    );

  const buildButton =
    document.getElementById(
      "buildTradeButton",
    );

  const notice =
    document.getElementById(
      "underlyingModeNotice",
    );

  document.body.dataset.underlying =
    underlying.toLowerCase();

  if (underlying === "QQQ") {
    if (!savedSpxTradeControls) {
      savedSpxTradeControls = {
        strategy:
          strategy?.value || "auto",
        dte:
          dte?.value || "1",
        wing:
          wing?.value || "25",
        contracts:
          contracts?.value || "1",
      };
    }

    setSelectValue(
      "strategySelector",
      "iron_condor",
    );

    setSelectValue(
      "dteSelector",
      "0",
    );

    setSelectValue(
      "wingWidthSelector",
      "5",
    );

    setSelectValue(
      "contractsSelector",
      "1",
    );

    setTradeControlsDisabled(true);

    if (buildButton) {
      buildButton.disabled = true;
      buildButton.textContent =
        "OBSERVATION ONLY";
    }

    if (notice) {
      notice.className =
        "underlying-mode-notice qqq-mode";

      notice.textContent =
        "QQQ | OBSERVATION ONLY | EXECUTION BLOCKED";
    }

    return;
  }

  setTradeControlsDisabled(false);

  if (savedSpxTradeControls) {
    setSelectValue(
      "strategySelector",
      savedSpxTradeControls.strategy,
    );

    setSelectValue(
      "dteSelector",
      savedSpxTradeControls.dte,
    );

    setSelectValue(
      "wingWidthSelector",
      savedSpxTradeControls.wing,
    );

    setSelectValue(
      "contractsSelector",
      savedSpxTradeControls.contracts,
    );
  }

  savedSpxTradeControls = null;

  if (buildButton) {
    buildButton.disabled = false;
    buildButton.textContent =
      "BUILD TRADE";
  }

  if (notice) {
    notice.className =
      "underlying-mode-notice spx-mode";

    notice.textContent =
      "SPX | STANDARD MODE";
  }
}


function htmlSafe(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function displayNumber(
  value,
  digits = 2,
) {
  const number = Number(value);

  return Number.isFinite(number)
    ? number.toFixed(digits)
    : "--";
}


function renderQqqObservationCard(data = {}) {
  if (
    getSelectedUnderlying() !== "QQQ"
  ) {
    return;
  }

  const card =
    document.getElementById(
      "bestTradeCard",
    );

  if (!card) {
    return;
  }

  const candidate =
    data.candidate_preview || null;

  const decision =
    data.qqq_decision || {};

  const stabilityScore =
    decision.stability_score ??
    data.stability_score_detail?.score ??
    null;

  const decisionText =
    decision.final_decision ??
    data.final_decision ??
    "NO TRADE";

  const reason =
    decision.reason_code ??
    data.decision_reason_code ??
    data.candidate_reason_code ??
    "QQQ_OBSERVATION_ONLY";

  const marketPermission =
    decision.market_permission ??
    data.market_permission ??
    "WAIT";

  if (!candidate) {
    card.innerHTML = `
      <div class="hero-header">
        <div>
          <div class="eyebrow">
            QQQ | OBSERVATION ONLY
          </div>

          <h1>No Candidate Available</h1>

          <div class="subline">
            QQQ price:
            ${displayNumber(data.price)}
            |
            Expected Move:
            ${displayNumber(
              data.expected_move,
            )}
          </div>
        </div>

        <div class="hero-badge no-trade">
          NO TRADE
        </div>
      </div>

      <div class="no-trade-message">
        ${htmlSafe(reason)}
      </div>
    `;

    return;
  }

  const strikes = [
    candidate.buy_put,
    candidate.sell_put,
    candidate.sell_call,
    candidate.buy_call,
  ]
    .map((value) =>
      displayNumber(value, 0),
    )
    .join(" / ");

  card.innerHTML = `
    <div class="hero-header">
      <div>
        <div class="eyebrow">
          QQQ | OBSERVATION ONLY
        </div>

        <h1>Iron Condor Candidate</h1>

        <div class="subline">
          ${strikes}
          |
          0 DTE
          |
          ${displayNumber(
            candidate.wing_width,
            0,
          )}-Point Wings
        </div>
      </div>

      <div class="hero-badge no-trade">
        ${htmlSafe(decisionText)}
      </div>
    </div>

    <div class="qqq-preview-grid">
      <div class="qqq-preview-item">
        <span>QQQ</span>
        <strong>
          ${displayNumber(
            data.price ??
            candidate.underlying_price,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>Expected Move</span>
        <strong>
          ${displayNumber(
            data.expected_move ??
            candidate.expected_move,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>Stability</span>
        <strong>
          ${
            stabilityScore !== null
              ? `${displayNumber(
                  stabilityScore,
                  1,
                )} / 100`
              : "--"
          }
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>Market Permission</span>
        <strong>
          ${htmlSafe(marketPermission)}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>Live Credit</span>
        <strong>
          $${displayNumber(
            candidate.live_credit,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>Max Profit</span>
        <strong>
          $${displayNumber(
            candidate.max_profit,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>Max Risk</span>
        <strong>
          $${displayNumber(
            candidate.max_risk,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>Return on Risk</span>
        <strong>
          ${displayNumber(
            candidate.return_on_risk,
          )}%
        </strong>
      </div>
    </div>

    <div class="qqq-observation-reason">
      <strong>
        Decision:
        ${htmlSafe(decisionText)}
      </strong>

      <span>
        ${htmlSafe(reason)}
      </span>

      <span>
        Candidate may be evaluated,
        but QQQ order execution remains blocked.
      </span>
    </div>
  `;
}


async function fetchLiveMarketSummary() {
  try {
    const response = await fetch(
      `/api/live-market?underlying=${
        encodeURIComponent(
          getSelectedUnderlying(),
        )
      }&_=${Date.now()}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `Live-market error ${response.status}`,
      );
    }

    const data = await response.json();

    updateMarketSummaryLiveData(data);

    renderQqqObservationCard(data);
  } catch (error) {
    console.error(
      "Live market summary failed:",
      error,
    );
  }
}

async function refreshDashboard() {
  if (dashboardRefreshInProgress) {
    return;
  }

  dashboardRefreshInProgress = true;

  try {
    await fetchRecommendation();

    await Promise.allSettled([
      fetchLiveMarketSummary(),
      loadBestTrade(),
      loadPositions(),
    ]);
  } finally {
    dashboardRefreshInProgress = false;
  }
}

function startDashboardRefresh() {
  if (dashboardRefreshTimer) {
    clearInterval(dashboardRefreshTimer);
  }

  refreshDashboard();

  dashboardRefreshTimer = setInterval(
    refreshDashboard,
    DASHBOARD_REFRESH_MS,
  );
}

document.addEventListener(
  "visibilitychange",
  () => {
    if (!document.hidden) {
      refreshDashboard();
    }
  },
);

updateClock();
startDashboardRefresh();

setInterval(
  updateClock,
  1000,
);

setInterval(
  updateApiFreshness,
  1000,
);

function initializeDashboardTabs() {
  const tabs = document.querySelectorAll(
    ".dashboard-tab",
  );

  const panels = document.querySelectorAll(
    ".dashboard-tab-panel",
  );

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetId = tab.dataset.tab;
      const targetPanel =
        document.getElementById(targetId);

      if (!targetPanel) {
        return;
      }

      tabs.forEach((item) => {
        item.classList.remove("active");
      });

      panels.forEach((panel) => {
        panel.classList.remove("active");
      });

      tab.classList.add("active");
      targetPanel.classList.add("active");
    });
  });
}

initializeTradeBuilder();
initializeDashboardTabs();


initializeSystemSettings();

initializeAuthUi();


function initializeUnderlyingSelector() {
  const selector =
    document.getElementById(
      "underlyingSelector",
    );

  if (!selector) {
    return;
  }

  applyUnderlyingMode();

  selector.addEventListener(
    "change",
    () => {
      applyUnderlyingMode();

      refreshDashboard();
    },
  );
}


if (document.readyState === "loading") {
  document.addEventListener(
    "DOMContentLoaded",
    initializeUnderlyingSelector,
    {
      once: true,
    },
  );
} else {
  initializeUnderlyingSelector();
}
