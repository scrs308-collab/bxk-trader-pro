import { initializeAuthUi } from "./auth-ui.js?v=3";

import {
  hasOwnerAccess,
  setAccessContext,
} from "./access-control.js?v=1";
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
} from "./best-trade.js?v=14";

import {
  loadPositions,
} from "./position.js";

import {
  initializeSystemSettings,
} from "./system-settings.js?v=1";


import {
  initializeAdminUsers,
} from "./admin-users.js?v=1";

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


async function fetchOvernightRisk() {
  try {
    const response = await fetch(
      `/api/overnight-risk?_=${Date.now()}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `Overnight risk error ${response.status}`,
      );
    }

    return await response.json();

  } catch (error) {
    console.error(
      "Overnight risk fetch failed:",
      error,
    );

    /*
     * Overnight monitoring must fail soft.
     * A GTH-data problem must never take down
     * the normal BXK dashboard.
     */
    return {
      available: false,
      observation_only: true,
      execution_authorized: false,
      state: "UNAVAILABLE",
      recommendation: "NONE",
      reason_code:
        "OVERNIGHT_RISK_FETCH_FAILED",
      session: {
        active: false,
        state: "UNKNOWN",
      },
    };
  }
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

    const [
      recentCondorRisk,
      overnightRisk,
    ] = await Promise.all([
      fetchRecentCondorRisk(),
      hasOwnerAccess()
        ? fetchOvernightRisk()
        : Promise.resolve({
            available: false,
            state: "UNAVAILABLE",
            reason_code:
              "OWNER_ACCESS_REQUIRED",
            positions: [],
            position_count: 0,
            execution_authorized: false,
          }),
    ]);

    const dashboardData = {
      ...data,
      recent_condor_risk:
        recentCondorRisk,
      overnight_risk:
        overnightRisk,
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
let currentUnderlyingDiscovery = null;
let underlyingDiscoveryInProgress = false;


function getSelectedUnderlying() {
  const control =
    document.getElementById(
      "underlyingSelector",
    );

  return String(
    control?.value || "SPX",
  )
    .trim()
    .toUpperCase();
}


function normalizeUnderlyingInput() {
  const control =
    document.getElementById(
      "underlyingSelector",
    );

  if (!control) {
    return "SPX";
  }

  const normalized = String(
    control.value || "",
  )
    .trim()
    .toUpperCase();

  control.value = normalized;

  return normalized;
}


function setSelectValue(id, value) {
  const control =
    document.getElementById(id);

  if (!control) {
    return;
  }

  control.value = String(value);
}


function captureSpxControls() {
  if (savedSpxTradeControls) {
    return;
  }

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

  savedSpxTradeControls = {
    strategy:
      strategy?.value || "auto",

    dte:
      dte?.value || "1",

    wing:
      wing?.value || "25",

    contracts:
      contracts?.value || "1",

    dteOptions:
      dte?.innerHTML || "",

    wingOptions:
      wing?.innerHTML || "",
  };
}


function restoreSpxControls() {
  if (!savedSpxTradeControls) {
    return;
  }

  const dte =
    document.getElementById(
      "dteSelector",
    );

  const wing =
    document.getElementById(
      "wingWidthSelector",
    );

  if (dte) {
    dte.innerHTML =
      savedSpxTradeControls.dteOptions;
  }

  if (wing) {
    wing.innerHTML =
      savedSpxTradeControls.wingOptions;
  }

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

  savedSpxTradeControls = null;
}


function setUnderlyingNotice(
  text,
  mode = "spx-mode",
) {
  const notice =
    document.getElementById(
      "underlyingModeNotice",
    );

  if (!notice) {
    return;
  }

  notice.className =
    `underlying-mode-notice ${mode}`;

  notice.textContent = text;
}


function setControlDisabled(
  id,
  disabled,
) {
  const control =
    document.getElementById(id);

  if (control) {
    control.disabled = disabled;
  }
}


function populateExpirationOptions(
  discovery,
) {
  const selector =
    document.getElementById(
      "dteSelector",
    );

  if (!selector) {
    return;
  }

  const expirations =
    Array.isArray(
      discovery?.expirations,
    )
      ? discovery.expirations
      : [];

  const seen = new Set();
  const choices = [];

  expirations.forEach(
    (expiration) => {
      const dte =
        Number(expiration?.dte);

      if (
        !Number.isFinite(dte) ||
        seen.has(dte)
      ) {
        return;
      }

      seen.add(dte);

      choices.push({
        dte,
        date:
          expiration.expiration_date ||
          "",
      });
    },
  );

  choices.sort(
    (a, b) => a.dte - b.dte,
  );

  selector.innerHTML = "";

  choices.forEach((choice) => {
    const option =
      document.createElement(
        "option",
      );

    option.value =
      String(choice.dte);

    option.textContent =
      choice.date
        ? `${choice.dte} DTE | ${choice.date}`
        : `${choice.dte} DTE`;

    selector.appendChild(option);
  });

  if (seen.has(0)) {
    selector.value = "0";
  }
}


function prepareUniversalWingSelector() {
  const wing =
    document.getElementById(
      "wingWidthSelector",
    );

  if (!wing) {
    return;
  }

  const baseOptions =
    savedSpxTradeControls?.wingOptions ||
    wing.innerHTML;

  wing.innerHTML =
    `<option value="">
       Select Width
     </option>${baseOptions}`;

  wing.value = "";
}


function applyUnderlyingMode(
  discovery = null,
) {
  const underlying =
    getSelectedUnderlying();

  const buildButton =
    document.getElementById(
      "buildTradeButton",
    );

  document.body.dataset.underlying =
    underlying.toLowerCase();

  // =============================================
  // SPX
  // Existing production behavior is preserved.
  // =============================================

  if (underlying === "SPX") {
    restoreSpxControls();

    currentUnderlyingDiscovery = null;

    [
      "strategySelector",
      "dteSelector",
      "wingWidthSelector",
      "contractsSelector",
    ].forEach((id) => {
      setControlDisabled(
        id,
        false,
      );
    });

    if (buildButton) {
      buildButton.disabled = false;
      buildButton.textContent =
        "BUILD TRADE";
    }

    setUnderlyingNotice(
      "SPX | STANDARD MODE",
      "spx-mode",
    );

    return;
  }

  captureSpxControls();

  // =============================================
  // QQQ
  // Keep the specialized QQQ engine for now.
  // =============================================

  if (underlying === "QQQ") {
    setSelectValue(
      "strategySelector",
      "iron_condor",
    );

    const dte =
      document.getElementById(
        "dteSelector",
      );

    if (dte) {
      dte.innerHTML =
        '<option value="0">0 DTE</option>';

      dte.value = "0";
    }

    const wing =
      document.getElementById(
        "wingWidthSelector",
      );

    if (
      wing &&
      savedSpxTradeControls
    ) {
      wing.innerHTML =
        savedSpxTradeControls
          .wingOptions;
    }

    setSelectValue(
      "wingWidthSelector",
      "5",
    );

    setSelectValue(
      "contractsSelector",
      "1",
    );

    [
      "strategySelector",
      "dteSelector",
      "wingWidthSelector",
      "contractsSelector",
    ].forEach((id) => {
      setControlDisabled(
        id,
        true,
      );
    });

    if (buildButton) {
      buildButton.disabled = true;
      buildButton.textContent =
        "OBSERVATION ONLY";
    }

    setUnderlyingNotice(
      "QQQ | OBSERVATION ONLY | EXECUTION BLOCKED",
      "qqq-mode",
    );

    return;
  }

  // =============================================
  // UNIVERSAL OPTION UNDERLYING
  // =============================================

  setSelectValue(
    "strategySelector",
    "iron_condor",
  );

  setSelectValue(
    "contractsSelector",
    "1",
  );

  setControlDisabled(
    "strategySelector",
    true,
  );

  setControlDisabled(
    "contractsSelector",
    true,
  );

  setControlDisabled(
    "dteSelector",
    false,
  );

  setControlDisabled(
    "wingWidthSelector",
    false,
  );

  if (discovery) {
    populateExpirationOptions(
      discovery,
    );

    prepareUniversalWingSelector();
  }

  if (buildButton) {
    buildButton.disabled = true;
    buildButton.textContent =
      "OBSERVATION ONLY";
  }

  const delivery =
    discovery?.delivery_style ||
    "DISCOVERING";

  const dteLabel =
    discovery?.has_0dte === true
      ? "0DTE AVAILABLE"
      : discovery
        ? "NO 0DTE TODAY"
        : "CHECKING CHAIN";

  setUnderlyingNotice(
    `${underlying} | ${delivery} | ${dteLabel} | EXECUTION BLOCKED`,
    "qqq-mode",
  );
}


async function loadUnderlyingDiscovery({
  refresh = true,
} = {}) {
  const underlying =
    normalizeUnderlyingInput();

  if (!underlying) {
    setUnderlyingNotice(
      "ENTER AN UNDERLYING SYMBOL",
      "qqq-mode",
    );

    return null;
  }

  if (underlying === "SPX") {
    applyUnderlyingMode();

    if (refresh) {
      refreshDashboard();
    }

    return null;
  }

  if (
    underlyingDiscoveryInProgress
  ) {
    return currentUnderlyingDiscovery;
  }

  underlyingDiscoveryInProgress =
    true;

  setUnderlyingNotice(
    `${underlying} | DISCOVERING OPTION CHAIN...`,
    "qqq-mode",
  );

  try {
    const response = await fetch(
      `/api/underlying-discovery?symbol=${
        encodeURIComponent(
          underlying,
        )
      }&_=${Date.now()}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `Discovery error ${response.status}`,
      );
    }

    const discovery =
      await response.json();

    if (
      discovery.options_available !==
      true
    ) {
      throw new Error(
        "No option chain available.",
      );
    }

    currentUnderlyingDiscovery =
      discovery;

    applyUnderlyingMode(
      discovery,
    );

    if (refresh) {
      refreshDashboard();
    }

    return discovery;
  } catch (error) {
    console.error(
      "Underlying discovery failed:",
      error,
    );

    currentUnderlyingDiscovery =
      null;

    setUnderlyingNotice(
      `${underlying} | UNAVAILABLE`,
      "qqq-mode",
    );

    return null;
  } finally {
    underlyingDiscoveryInProgress =
      false;
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



function renderUniversalObservationCard(
  data = {},
) {
  const card =
    document.getElementById(
      "bestTradeCard",
    );

  if (!card) {
    return;
  }

  const symbol =
    String(
      data.symbol ||
      getSelectedUnderlying(),
    ).toUpperCase();

  const candidate =
    data.candidate_preview || null;

  const reason =
    data.reason_code ||
    "OBSERVATION_ONLY";

  const delivery =
    data.delivery_style ||
    currentUnderlyingDiscovery
      ?.delivery_style ||
    "--";

  if (!candidate) {
    card.innerHTML = `
      <div class="hero-header">
        <div>
          <div class="eyebrow">
            ${htmlSafe(symbol)}
            | UNIVERSAL ANALYSIS
          </div>

          <h1>
            Observation Only
          </h1>

          <div class="subline">
            Price:
            ${displayNumber(data.price)}
            |
            Delivery:
            ${htmlSafe(delivery)}
          </div>
        </div>

        <div class="hero-badge no-trade">
          BLOCKED
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
          ${htmlSafe(symbol)}
          | UNIVERSAL ANALYSIS
        </div>

        <h1>
          Iron Condor Candidate
        </h1>

        <div class="subline">
          ${strikes}
          |
          ${candidate.dte ?? "--"} DTE
          |
          ${displayNumber(
            candidate.wing_width,
            0,
          )}-Point Wings
        </div>
      </div>

      <div class="hero-badge no-trade">
        OBSERVE
      </div>
    </div>

    <div class="qqq-preview-grid">

      <div class="qqq-preview-item">
        <span>
          ${htmlSafe(symbol)}
        </span>
        <strong>
          ${displayNumber(
            data.price ??
            candidate.underlying_price,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>
          Expected Move
        </span>
        <strong>
          ${displayNumber(
            data.expected_move ??
            candidate.expected_move,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>
          Delivery
        </span>
        <strong>
          ${htmlSafe(delivery)}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>
          Profile
        </span>
        <strong>
          ${
            data.verified_profile
              ? "VERIFIED"
              : "DISCOVERED"
          }
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>
          Live Credit
        </span>
        <strong>
          $${displayNumber(
            candidate.live_credit,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>
          Max Profit
        </span>
        <strong>
          $${displayNumber(
            candidate.max_profit,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>
          Max Risk
        </span>
        <strong>
          $${displayNumber(
            candidate.max_risk,
          )}
        </strong>
      </div>

      <div class="qqq-preview-item">
        <span>
          Return on Risk
        </span>
        <strong>
          ${displayNumber(
            candidate.return_on_risk,
          )}%
        </strong>
      </div>
    </div>

    <div class="qqq-observation-reason">
      <strong>
        ANALYSIS READY
      </strong>

      <span>
        ${htmlSafe(reason)}
      </span>

      <span>
        Universal analysis only.
        Order execution remains blocked.
      </span>
    </div>
  `;
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
  const underlying =
    getSelectedUnderlying();

  try {

    // =============================================
    // VERIFIED SPX / QQQ LIVE ENGINES
    // =============================================

    if (
      underlying === "SPX" ||
      underlying === "QQQ"
    ) {
      const response = await fetch(
        `/api/live-market?underlying=${
          encodeURIComponent(
            underlying,
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

      const data =
        await response.json();

      updateMarketSummaryLiveData(
        data,
      );

      if (underlying === "QQQ") {
        renderQqqObservationCard(
          data,
        );
      }

      return;
    }

    // =============================================
    // UNIVERSAL UNDERLYING
    // =============================================

    if (
      !currentUnderlyingDiscovery ||
      currentUnderlyingDiscovery.symbol !==
        underlying
    ) {
      await loadUnderlyingDiscovery({
        refresh: false,
      });
    }

    if (
      !currentUnderlyingDiscovery
    ) {
      renderUniversalObservationCard({
        symbol: underlying,
        reason_code:
          "DISCOVERY_UNAVAILABLE",
      });

      return;
    }

    const dteControl =
      document.getElementById(
        "dteSelector",
      );

    const wingControl =
      document.getElementById(
        "wingWidthSelector",
      );

    const dte =
      Number(
        dteControl?.value,
      );

    const wingWidth =
      Number(
        wingControl?.value,
      );

    if (
      !Number.isFinite(dte) ||
      !Number.isFinite(wingWidth) ||
      wingWidth <= 0
    ) {
      renderUniversalObservationCard({
        symbol: underlying,
        price:
          currentUnderlyingDiscovery
            .price,
        delivery_style:
          currentUnderlyingDiscovery
            .delivery_style,
        verified_profile:
          currentUnderlyingDiscovery
            .verified_profile,
        reason_code:
          "SELECT_EXPIRATION_AND_WING_WIDTH",
      });

      return;
    }

    const params =
      new URLSearchParams({
        symbol: underlying,
        dte: String(dte),
        wing_width:
          String(wingWidth),
        _: Date.now().toString(),
      });

    const response = await fetch(
      `/api/underlying-analysis?${
        params.toString()
      }`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `Underlying-analysis error ${
          response.status
        }`,
      );
    }

    const data =
      await response.json();

    renderUniversalObservationCard(
      data,
    );

  } catch (error) {
    console.error(
      "Live market summary failed:",
      error,
    );

    if (
      underlying !== "SPX"
    ) {
      renderUniversalObservationCard({
        symbol: underlying,
        reason_code:
          "UNDERLYING_ANALYSIS_ERROR",
      });
    }
  }
}


async function refreshDashboard() {
  if (dashboardRefreshInProgress) {
    return;
  }

  dashboardRefreshInProgress = true;

  try {
    const underlying =
      getSelectedUnderlying();

    if (underlying === "SPX") {
      await fetchRecommendation();

      const refreshTasks = [
        fetchLiveMarketSummary(),
        loadBestTrade(),
      ];

      if (hasOwnerAccess()) {
        refreshTasks.push(
          loadPositions(),
        );
      }

      await Promise.allSettled(
        refreshTasks
      );

      return;
    }

    /*
     * Non-SPX mode deliberately avoids running the
     * SPX Best Trade / recommendation engines.
     */
    const refreshTasks = [
      fetchLiveMarketSummary(),
    ];

    if (hasOwnerAccess()) {
      refreshTasks.push(
        loadPositions(),
      );
    }

    await Promise.allSettled(
      refreshTasks
    );

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

function applyOwnerVisibility() {
  const ownerAccess =
    hasOwnerAccess();

  document
    .querySelectorAll(
      '[data-owner-only="true"]',
    )
    .forEach((element) => {
      element.hidden = !ownerAccess;
    });
}


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


async function initializeDashboardApplication() {
  const authStatus =
    await initializeAuthUi();

  setAccessContext(
    authStatus
  );

  applyOwnerVisibility();

  initializeTradeBuilder();
  initializeDashboardTabs();
  initializeUnderlyingSelector();

  if (hasOwnerAccess()) {
    initializeSystemSettings();
    initializeAdminUsers();
  }

  startDashboardRefresh();
}


if (document.readyState === "loading") {
  document.addEventListener(
    "DOMContentLoaded",
    initializeDashboardApplication,
    {
      once: true,
    },
  );
} else {
  initializeDashboardApplication();
}
