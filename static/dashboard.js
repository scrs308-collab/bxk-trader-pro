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
} from "./system-settings.js?v=2";


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



const TRADE_JOURNAL_CACHE_MS =
  60 * 1000;

let tradeJournalPerformanceLoadedAt = 0;
let tradeJournalPerformanceInFlight = null;


function escapeJournalHtml(value) {
  return String(
    value ?? "",
  )
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function journalCurrency(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  return number.toLocaleString(
    "en-US",
    {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    },
  );
}


function journalNumber(
  value,
  digits = 2,
) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  return number.toLocaleString(
    "en-US",
    {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    },
  );
}


function journalDateTime(value) {
  if (!value) {
    return "--";
  }

  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return String(value);
  }

  return date.toLocaleString();
}


function journalPnlClass(value) {
  const number = Number(value);

  if (number > 0.01) {
    return "journal-positive";
  }

  if (number < -0.01) {
    return "journal-negative";
  }

  return "journal-neutral";
}


function journalStatCard(
  label,
  value,
  cssClass = "",
  detail = "",
) {
  return `
    <div class="journal-stat">
      <div class="journal-stat-label">
        ${escapeJournalHtml(label)}
      </div>

      <div class="journal-stat-value ${cssClass}">
        ${escapeJournalHtml(value)}
      </div>

      ${
        detail
          ? `
            <div class="journal-stat-detail">
              ${escapeJournalHtml(detail)}
            </div>
          `
          : ""
      }
    </div>
  `;
}


function renderTradeJournalSummary(
  summary,
) {
  const target =
    document.getElementById(
      "journalPerformanceSummary",
    );

  if (!target) {
    return;
  }

  if (!summary?.available) {
    target.innerHTML = `
      <div class="journal-loading">
        Journal reporting is unavailable.
      </div>
    `;
    return;
  }

  const totalTrades =
    Number(summary.total_trades || 0);

  const wins =
    Number(summary.wins || 0);

  const losses =
    Number(summary.losses || 0);

  const scratches =
    Number(summary.scratches || 0);

  let profitFactor = "--";

  if (
    summary.profit_factor !== null
    && summary.profit_factor !== undefined
  ) {
    profitFactor = journalNumber(
      summary.profit_factor,
      2,
    );
  } else if (
    wins > 0
    && losses === 0
  ) {
    profitFactor = "?";
  }

  const bestTrade =
    summary.best_trade;

  const worstTrade =
    summary.worst_trade;

  const threats =
    summary.threat_counts || {};

  const exits =
    summary.exit_reasons || {};

  const cards = [
    journalStatCard(
      "Completed Trades",
      totalTrades,
      "",
      `${summary.open_trades || 0} currently open`,
    ),

    journalStatCard(
      "Win Rate",
      `${journalNumber(
        summary.win_rate || 0,
        1,
      )}%`,
      "",
      `${wins} W / ${losses} L / ${scratches} scratch`,
    ),

    journalStatCard(
      "Realized P/L",
      journalCurrency(
        summary.total_realized_pnl,
      ),
      journalPnlClass(
        summary.total_realized_pnl,
      ),
    ),

    journalStatCard(
      "Average Trade",
      journalCurrency(
        summary.average_pnl,
      ),
      journalPnlClass(
        summary.average_pnl,
      ),
    ),

    journalStatCard(
      "Profit Factor",
      profitFactor,
    ),

    journalStatCard(
      "Average Winner",
      journalCurrency(
        summary.average_winner,
      ),
      "journal-positive",
    ),

    journalStatCard(
      "Average Loser",
      journalCurrency(
        summary.average_loser,
      ),
      Number(
        summary.average_loser,
      ) < 0
        ? "journal-negative"
        : "",
    ),

    journalStatCard(
      "Best Trade",
      bestTrade
        ? journalCurrency(
            bestTrade.realized_pnl,
          )
        : "--",
      bestTrade
        ? journalPnlClass(
            bestTrade.realized_pnl,
          )
        : "",
      bestTrade
        ? journalDateTime(
            bestTrade.closed_at,
          )
        : "",
    ),

    journalStatCard(
      "Worst Trade",
      worstTrade
        ? journalCurrency(
            worstTrade.realized_pnl,
          )
        : "--",
      worstTrade
        ? journalPnlClass(
            worstTrade.realized_pnl,
          )
        : "",
      worstTrade
        ? journalDateTime(
            worstTrade.closed_at,
          )
        : "",
    ),

    journalStatCard(
      "Avg Min Cushion",
      summary.average_min_short_cushion
        === null
        ? "--"
        : `${
            journalNumber(
              summary.average_min_short_cushion,
              1,
            )
          } pts`,
    ),

    journalStatCard(
      "Risk Escalations",
      `${threats.critical || 0} CRITICAL`,
      Number(
        threats.critical || 0,
      ) > 0
        ? "journal-negative"
        : "",
      `${threats.red || 0} RED / ${threats.orange || 0} ORANGE`,
    ),

    journalStatCard(
      "Exit Mix",
      `${exits.broker_close || 0} closed`,
      "",
      `${
        exits.expired_worthless || 0
      } expired / ${
        exits.cash_settlement || 0
      } settled`,
    ),
  ];

  target.innerHTML =
    cards.join("");
}


function renderTradeJournalTrades(
  payload,
) {
  const target =
    document.getElementById(
      "journalRecentTrades",
    );

  if (!target) {
    return;
  }

  const trades =
    payload?.trades || [];

  if (!payload?.available) {
    target.innerHTML = `
      <div class="journal-loading">
        Journal history is unavailable.
      </div>
    `;
    return;
  }

  if (!trades.length) {
    target.innerHTML = `
      <div class="journal-loading">
        No completed journal trades yet.
      </div>
    `;
    return;
  }

  const rows = trades.map(
    (trade) => {
      const strikes = [
        trade.long_put,
        trade.short_put,
        trade.short_call,
        trade.long_call,
      ]
        .filter(
          (value) =>
            value !== null
            && value !== undefined,
        )
        .join(" / ");

      return `
        <tr>
          <td>
            ${escapeJournalHtml(
              journalDateTime(
                trade.closed_at,
              ),
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              trade.underlying || "--",
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              trade.strategy || "--",
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              trade.dte ?? "--",
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              trade.quantity ?? "--",
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              strikes || "--",
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              journalCurrency(
                trade.entry_fill_credit,
              ),
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              journalCurrency(
                trade.exit_debit,
              ),
            )}
          </td>

          <td
            class="${
              journalPnlClass(
                trade.realized_pnl,
              )
            }"
          >
            ${escapeJournalHtml(
              journalCurrency(
                trade.realized_pnl,
              ),
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              trade.outcome || "--",
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              trade.worst_threat_state
              || "GREEN",
            )}
          </td>

          <td>
            ${escapeJournalHtml(
              trade.exit_reason || "--",
            )}
          </td>
        </tr>
      `;
    },
  );

  target.innerHTML = `
    <div class="journal-table-wrap">
      <table class="journal-trade-table">
        <thead>
          <tr>
            <th>Closed</th>
            <th>Symbol</th>
            <th>Strategy</th>
            <th>DTE</th>
            <th>Qty</th>
            <th>Strikes</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>P/L</th>
            <th>Result</th>
            <th>Worst Risk</th>
            <th>Exit Reason</th>
          </tr>
        </thead>

        <tbody>
          ${rows.join("")}
        </tbody>
      </table>
    </div>
  `;
}


async function loadTradeJournalPerformance(
  force = false,
) {
  if (!hasOwnerAccess()) {
    return;
  }

  const now = Date.now();

  if (
    !force
    && tradeJournalPerformanceLoadedAt
    && (
      now
      - tradeJournalPerformanceLoadedAt
    ) < TRADE_JOURNAL_CACHE_MS
  ) {
    return;
  }

  if (tradeJournalPerformanceInFlight) {
    return tradeJournalPerformanceInFlight;
  }

  const status =
    document.getElementById(
      "journalPerformanceStatus",
    );

  if (status) {
    status.textContent =
      "Loading journal performance...";
  }

  tradeJournalPerformanceInFlight =
    (async () => {
      try {
        const [
          summaryResponse,
          tradesResponse,
        ] = await Promise.all([
          fetch(
            `/api/trade-journal/summary?_=${Date.now()}`,
            {
              cache: "no-store",
            },
          ),

          fetch(
            `/api/trade-journal/trades?limit=25&_=${Date.now()}`,
            {
              cache: "no-store",
            },
          ),
        ]);

        if (!summaryResponse.ok) {
          throw new Error(
            `Summary HTTP ${
              summaryResponse.status
            }`,
          );
        }

        if (!tradesResponse.ok) {
          throw new Error(
            `Trades HTTP ${
              tradesResponse.status
            }`,
          );
        }

        const [
          summary,
          trades,
        ] = await Promise.all([
          summaryResponse.json(),
          tradesResponse.json(),
        ]);

        renderTradeJournalSummary(
          summary,
        );

        renderTradeJournalTrades(
          trades,
        );

        tradeJournalPerformanceLoadedAt =
          Date.now();

        if (status) {
          status.textContent =
            `Updated ${
              new Date().toLocaleTimeString()
            }`;
        }

      } catch (error) {
        console.error(
          "Trade journal performance failed:",
          error,
        );

        if (status) {
          status.textContent =
            "Performance data unavailable.";
        }

        const summaryTarget =
          document.getElementById(
            "journalPerformanceSummary",
          );

        if (summaryTarget) {
          summaryTarget.innerHTML = `
            <div class="journal-loading">
              Unable to load journal performance.
            </div>
          `;
        }
      } finally {
        tradeJournalPerformanceInFlight =
          null;
      }
    })();

  return tradeJournalPerformanceInFlight;
}


function initializeTradeJournalPerformanceControls() {
  const refreshButton =
    document.getElementById(
      "journalRefreshButton",
    );

  if (refreshButton) {
    refreshButton.addEventListener(
      "click",
      () => {
        loadTradeJournalPerformance(
          true,
        );
      },
    );
  }
}

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

      if (
        targetId === "performanceTab"
        && hasOwnerAccess()
      ) {
        loadTradeJournalPerformance();
      }
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
  initializeTradeJournalPerformanceControls();
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
