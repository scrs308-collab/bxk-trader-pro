import { initializeAuthUi } from "./auth-ui.js?v=3";

import {
  hasOwnerAccess,
  hasTradingAccess,
  setAccessContext,
} from "./access-control.js?v=2";

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
} from "./best-trade.js?v=16";

import {
  loadPositions,
} from "./position.js?v=6";

import {
  initializeSystemSettings,
} from "./system-settings.js?v=2";


import {
  initializeAdminUsers,
} from "./admin-users.js?v=2";

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


let positionAccessEnabled = false;

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

      if (positionAccessEnabled) {
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

    if (positionAccessEnabled) {
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

  const carry =
    summary.carry_learning || {};

  const ratioBuckets =
    carry.ratio_buckets || {};

  const carryPercent = (value) => {
    if (
      value === null
      || value === undefined
    ) {
      return "--";
    }

    return `${
      journalNumber(value, 1)
    }%`;
  };

  const carryAveragePnl = (bucket) => {
    if (
      !bucket
      || !Number(
        bucket.held_completed_trades || 0
      )
      || bucket.held_average_realized_pnl
        === null
      || bucket.held_average_realized_pnl
        === undefined
    ) {
      return "--";
    }

    return journalCurrency(
      bucket.held_average_realized_pnl,
    );
  };

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

  const carryCards = [
    journalStatCard(
      "Carry Learning",
      Number(
        carry.evaluated_trades || 0
      ),
      "",
      `${
        carry.held_overnight || 0
      } held overnight / ${
        carry.next_open_observations || 0
      } next-open observations`,
    ),

    journalStatCard(
      "Next-Open Breach",
      carryPercent(
        carry.breach_rate,
      ),
      Number(
        carry.short_breaches || 0
      ) > 0
        ? "journal-negative"
        : "",
      `${
        carry.short_breaches || 0
      } breaches / ${
        carry.next_open_observations || 0
      } observed`,
    ),

    journalStatCard(
      "Held Carry P/L",
      Number(
        carry.held_completed_trades || 0
      ) > 0
        ? journalCurrency(
            carry.held_total_realized_pnl,
          )
        : "--",
      Number(
        carry.held_completed_trades || 0
      ) > 0
        ? journalPnlClass(
            carry.held_total_realized_pnl,
          )
        : "",
      `${
        carry.held_completed_trades || 0
      } completed / avg ${
        Number(
          carry.held_completed_trades || 0
        ) > 0
          ? journalCurrency(
              carry.held_average_realized_pnl,
            )
          : "--"
      }`,
    ),
  ];

  const ratioCards = [
    [
      "Carry < 0.50",
      ratioBuckets.lt_0_50,
    ],
    [
      "Carry 0.50-0.74",
      ratioBuckets["0_50_to_0_74"],
    ],
    [
      "Carry 0.75-0.99",
      ratioBuckets["0_75_to_0_99"],
    ],
    [
      "Carry >= 1.00",
      ratioBuckets.gte_1_00,
    ],
  ].map(
    ([label, bucket]) => {
      const data = bucket || {};

      const observations = Number(
        data.next_open_observations || 0
      );

      return journalStatCard(
        label,
        carryPercent(
          data.breach_rate,
        ),
        Number(
          data.short_breaches || 0
        ) > 0
          ? "journal-negative"
          : "",
        `n=${
          data.trades || 0
        } / ${
          observations
        } opens / avg P/L ${
          carryAveragePnl(data)
        }`,
      );
    },
  );

  target.innerHTML = [
    ...cards,
    ...carryCards,
    ...ratioCards,
  ].join("");
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
  if (!hasTradingAccess()) {
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
        && hasTradingAccess()
      ) {
        loadTradeJournalPerformance();
      }
    });
  });
}

function applyAuthenticatedVisibility(authStatus) {
  const authenticatedAccess = Boolean(
    authStatus &&
    (
      authStatus.enabled === false ||
      authStatus.authenticated === true
    )
  );

  document
    .querySelectorAll(
      '[data-authenticated-only="true"]',
    )
    .forEach((element) => {
      element.hidden = !authenticatedAccess;
    });

  return authenticatedAccess;
}


function applyTradingVisibility() {
  const tradingAccess =
    hasTradingAccess();

  document
    .querySelectorAll(
      '[data-trading-only="true"]',
    )
    .forEach((element) => {
      element.hidden = !tradingAccess;
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



let accountStatusAuth = null;
let accountStatusListenerBound = false;


function hasPrivateTradingAccess(
  authStatus,
) {
  if (!authStatus) {
    return false;
  }

  if (authStatus.enabled === false) {
    return true;
  }

  if (authStatus.authenticated !== true) {
    return false;
  }

  const role = String(
    authStatus.role || "",
  ).trim().toUpperCase();

  return (
    role === "OWNER" ||
    role === "BETA"
  );
}


function accountStatusMetric(
  label,
  value,
) {
  return `
    <div
      style="
        padding:12px 14px;
        border:1px solid rgba(148,163,184,.28);
        border-radius:10px;
        min-width:0;
      "
    >
      <div
        style="
          font-size:11px;
          font-weight:700;
          opacity:.68;
          margin-bottom:5px;
          text-transform:uppercase;
          letter-spacing:.05em;
        "
      >
        ${htmlSafe(label)}
      </div>

      <div
        style="
          font-size:15px;
          font-weight:800;
          overflow-wrap:anywhere;
        "
      >
        ${htmlSafe(value)}
      </div>
    </div>
  `;
}


function ensureAccountStatusBanner() {
  let banner =
    document.getElementById(
      "accountStatusBanner",
    );

  if (banner) {
    return banner;
  }

  banner =
    document.createElement(
      "section",
    );

  banner.id =
    "accountStatusBanner";

  banner.className = "card";

  banner.style.marginBottom =
    "14px";

  const tabs =
    document.querySelector(
      ".dashboard-tabs",
    );

  if (tabs) {
    tabs.insertAdjacentElement(
      "beforebegin",
      banner,
    );

    return banner;
  }

  const firstPanel =
    document.querySelector(
      ".dashboard-tab-panel",
    );

  if (
    firstPanel &&
    firstPanel.parentElement
  ) {
    firstPanel.parentElement.insertBefore(
      banner,
      firstPanel,
    );

    return banner;
  }

  const main =
    document.querySelector("main");

  if (main) {
    main.prepend(banner);
    return banner;
  }

  document.body.prepend(banner);

  return banner;
}


function brokerActionButton(
  label,
  action,
  {
    broker = "",
    accountId = "",
    disabled = false,
  } = {},
) {
  const brokerAttribute =
    broker
      ? ` data-broker="${htmlSafe(broker)}"`
      : "";

  const accountAttribute =
    accountId
      ? ` data-account-id="${htmlSafe(accountId)}"`
      : "";

  const disabledAttribute =
    disabled
      ? " disabled"
      : "";

  return `
    <button
      type="button"
      data-bxk-broker-action="${htmlSafe(action)}"
      ${brokerAttribute}
      ${accountAttribute}
      ${disabledAttribute}
      style="
        border:1px solid rgba(148,163,184,.30);
        border-radius:8px;
        padding:7px 10px;
        background:rgba(15,23,42,.16);
        color:inherit;
        font:inherit;
        font-size:12px;
        font-weight:700;
        cursor:${disabled ? "default" : "pointer"};
        opacity:${disabled ? ".62" : "1"};
      "
    >
      ${htmlSafe(label)}
    </button>
  `;
}


async function fetchBrokerJson(
  url,
  options = {},
) {
  const response = await fetch(
    url,
    {
      cache: "no-store",
      ...options,
    },
  );

  let data = null;

  try {
    data = await response.json();
  } catch (_error) {
    data = null;
  }

  if (!response.ok) {
    const detail =
      data &&
      typeof data === "object"
        ? data.detail
        : null;

    throw new Error(
      detail ||
      `Broker request failed with HTTP ${response.status}`,
    );
  }

  return data;
}


async function optionalBrokerJson(
  url,
  fallback,
) {
  try {
    return await fetchBrokerJson(
      url,
    );
  } catch (error) {
    console.warn(
      "Optional broker request failed:",
      url,
      error,
    );

    return fallback;
  }
}


function brokerPreferenceEntry(
  preferences,
  brokerName,
) {
  const brokers =
    Array.isArray(
      preferences?.brokers,
    )
      ? preferences.brokers
      : [];

  return (
    brokers.find(
      (item) =>
        String(
          item?.broker || "",
        )
          .trim()
          .toLowerCase()
        === brokerName,
    )
    || null
  );
}


function renderSchwabAccounts(
  accounts,
) {
  if (
    !Array.isArray(accounts)
    || accounts.length === 0
  ) {
    return `
      <div
        style="
          margin-top:8px;
          opacity:.68;
          font-size:12px;
          line-height:1.45;
        "
      >
        No authorized Schwab accounts are available yet.
      </div>
    `;
  }

  return accounts
    .filter(
      (account) =>
        account &&
        account.is_active !== false,
    )
    .map(
      (account) => {
        const selected =
          account.is_default === true;

        const label =
          account.account_number_masked
          || account.nickname
          || "Authorized account";

        const type =
          account.account_type
          || "";

        const accountId =
          account.id
          || "";

        const action =
          selected
            ? brokerActionButton(
                "SELECTED",
                "none",
                {
                  disabled: true,
                },
              )
            : brokerActionButton(
                "Select account",
                "select-schwab-account",
                {
                  accountId,
                  disabled: !accountId,
                },
              );

        return `
          <div
            style="
              display:flex;
              align-items:center;
              justify-content:space-between;
              gap:10px;
              padding:8px 0;
              border-top:
                1px solid rgba(148,163,184,.16);
            "
          >
            <div
              style="
                min-width:0;
                font-size:12px;
                line-height:1.4;
              "
            >
              <strong>
                ${htmlSafe(label)}
              </strong>

              ${
                type
                  ? `
                    <div
                      style="
                        opacity:.62;
                        margin-top:2px;
                      "
                    >
                      ${htmlSafe(type)}
                    </div>
                  `
                  : ""
              }
            </div>

            ${action}
          </div>
        `;
      },
    )
    .join("");
}


function bindAccountStatusActions(
  banner,
) {
  if (
    banner.dataset.bxkBrokerActionsBound
    === "1"
  ) {
    return;
  }

  banner.dataset.bxkBrokerActionsBound =
    "1";

  banner.addEventListener(
    "click",
    async (event) => {
      const button =
        event.target.closest(
          "[data-bxk-broker-action]",
        );

      if (
        !button
        || !banner.contains(button)
      ) {
        return;
      }

      const action =
        String(
          button.dataset.bxkBrokerAction
          || "",
        ).trim();

      if (
        !action
        || action === "none"
      ) {
        return;
      }

      const originalText =
        button.textContent;

      button.disabled = true;
      button.textContent =
        "WORKING...";

      try {
        if (
          action === "connect-schwab"
        ) {
          window.location.assign(
            "/api/broker-connection/schwab/connect",
          );

          return;
        }

        if (
          action === "select-broker"
        ) {
          const brokerName =
            String(
              button.dataset.broker
              || "",
            )
              .trim()
              .toLowerCase();

          if (!brokerName) {
            throw new Error(
              "Broker selection is missing.",
            );
          }

          await fetchBrokerJson(
            (
              "/api/broker-connection/brokers/"
              + encodeURIComponent(
                  brokerName,
                )
              + "/select"
            ),
            {
              method: "POST",
            },
          );
        }

        if (
          action ===
          "select-schwab-account"
        ) {
          const accountId =
            String(
              button.dataset.accountId
              || "",
            ).trim();

          if (!accountId) {
            throw new Error(
              "Schwab account selection is missing.",
            );
          }

          await fetchBrokerJson(
            (
              "/api/broker-connection/schwab/accounts/"
              + encodeURIComponent(
                  accountId,
                )
              + "/select"
            ),
            {
              method: "POST",
            },
          );
        }

        window.dispatchEvent(
          new CustomEvent(
            "bxk:broker-connection-changed",
            {
              detail: {
                source:
                  "dashboard-broker-controls",
              },
            },
          ),
        );

      } catch (error) {
        console.error(
          "Broker action failed:",
          error,
        );

        button.disabled = false;
        button.textContent =
          "FAILED";

        window.setTimeout(
          () => {
            if (
              button.isConnected
            ) {
              button.textContent =
                originalText;

              button.disabled = false;
            }
          },
          1800,
        );
      }
    },
  );
}


async function refreshAccountStatusBanner() {
  const authStatus =
    accountStatusAuth;

  if (
    !hasPrivateTradingAccess(
      authStatus,
    )
  ) {
    return;
  }

  const banner =
    ensureAccountStatusBanner();

  bindAccountStatusActions(
    banner,
  );

  banner.innerHTML = `
    <div class="card-label">
      Account & Trading Status
    </div>

    <div
      style="
        margin-top:10px;
        opacity:.72;
        font-size:13px;
      "
    >
      Checking your broker connections...
    </div>
  `;

  try {
    const preferences =
      await fetchBrokerJson(
        (
          "/api/broker-connection/brokers"
          + `?_=${Date.now()}`
        ),
      );

    const [
      tastytrade,
      schwabAccounts,
    ] = await Promise.all([
      optionalBrokerJson(
        (
          "/api/broker-connection/status"
          + `?_=${Date.now()}`
        ),
        {
          connected: false,
          verified: false,
          live_trading_enabled: false,
        },
      ),

      optionalBrokerJson(
        (
          "/api/broker-connection/schwab/accounts"
          + `?_=${Date.now()}`
        ),
        [],
      ),
    ]);

    const role = String(
      authStatus.role || "OWNER",
    )
      .trim()
      .toUpperCase();

    const username = String(
      authStatus.username || "",
    ).trim();

    const preferredBroker =
      String(
        preferences?.preferred_broker
        || "tastytrade",
      )
        .trim()
        .toLowerCase();

    const tastyPreference =
      brokerPreferenceEntry(
        preferences,
        "tastytrade",
      );

    const schwabPreference =
      brokerPreferenceEntry(
        preferences,
        "schwab",
      );

    const tastyConnected =
      tastytrade?.connected === true
      && tastytrade?.verified === true;

    const tastyAvailable =
      tastyConnected
      || tastyPreference?.available === true;

    const live =
      tastyConnected
      && tastytrade
        ?.live_trading_enabled === true;

    const tastyAccount =
      tastyConnected
        ? (
            tastytrade
              ?.account_number_masked
            || "Connected"
          )
        : "--";

    const schwabAccountList =
      Array.isArray(
        schwabAccounts,
      )
        ? schwabAccounts
        : (
            Array.isArray(
              schwabAccounts?.accounts,
            )
              ? schwabAccounts.accounts
              : []
          );

    const activeSchwabAccounts =
      schwabAccountList.filter(
        (account) =>
          account
          && account.is_active !== false,
      );

    const selectedSchwabAccount =
      activeSchwabAccounts.find(
        (account) =>
          account.is_default === true,
      )
      || null;

    const schwabConnected =
      activeSchwabAccounts.length > 0;

    const schwabAvailable =
      schwabPreference?.available === true;

    const schwabAccount =
      selectedSchwabAccount
        ? (
            selectedSchwabAccount
              .account_number_masked
            || selectedSchwabAccount
              .nickname
            || "Selected"
          )
        : (
            schwabConnected
              ? "SELECT ACCOUNT"
              : "--"
          );

    const dataSource =
      preferredBroker === "schwab"
        ? "SCHWAB"
        : "TASTYTRADE";

    const tradingState =
      live
        ? "LIVE ENABLED"
        : "SAFE MODE";

    const tastyDataAction =
      preferredBroker === "tastytrade"
        ? brokerActionButton(
            "ACCOUNT DATA SOURCE",
            "none",
            {
              disabled: true,
            },
          )
        : (
            tastyAvailable
              ? brokerActionButton(
                  "Use for account data",
                  "select-broker",
                  {
                    broker:
                      "tastytrade",
                  },
                )
              : ""
          );

    const schwabDataAction =
      preferredBroker === "schwab"
        ? brokerActionButton(
            "ACCOUNT DATA SOURCE",
            "none",
            {
              disabled: true,
            },
          )
        : (
            schwabAvailable
              ? brokerActionButton(
                  "Use for account data",
                  "select-broker",
                  {
                    broker:
                      "schwab",
                  },
                )
              : ""
          );

    const schwabConnectAction =
      brokerActionButton(
        (
          schwabConnected
            ? "Reconnect Schwab"
            : "Connect Schwab"
        ),
        "connect-schwab",
      );

    let executionNote = "";

    if (live) {
      executionNote =
        "Live order submission is enabled. " +
        "Orders continue to execute through Tastytrade.";
    } else if (role === "BETA") {
      executionNote =
        "SAFE MODE is active, so real orders cannot " +
        "be submitted. Live access must be enabled " +
        "by the BXK OWNER.";
    } else {
      executionNote =
        "SAFE MODE is active, so real orders cannot " +
        "be submitted while live trading is disabled.";
    }

    const callbackParameters =
      new URLSearchParams(
        window.location.search,
      );

    const callbackBroker =
      String(
        callbackParameters.get("broker")
        || "",
      )
        .trim()
        .toLowerCase();

    const callbackStatus =
      String(
        callbackParameters.get("status")
        || "",
      )
        .trim()
        .toLowerCase();

    let callbackMessage = "";

    if (callbackBroker === "schwab") {
      if (
        callbackStatus === "connected"
      ) {
        callbackMessage =
          "Schwab authorization completed successfully.";
      } else if (
        callbackStatus === "select-account"
      ) {
        callbackMessage =
          "Schwab is connected. Select the account " +
          "BXK should use for account data.";
      } else if (
        callbackStatus === "error"
      ) {
        callbackMessage =
          "Schwab authorization needs attention. " +
          "Use Reconnect Schwab to try again.";
      }
    }

    banner.innerHTML = `
      <div class="card-label">
        Account & Trading Status
      </div>

      <div
        style="
          margin-top:5px;
          margin-bottom:12px;
          opacity:.72;
          font-size:13px;
        "
      >
        ${
          username
            ? `Signed in as ${htmlSafe(username)}`
            : "BXK Trader Pro"
        }
      </div>

      ${
        callbackMessage
          ? `
            <div
              style="
                margin-bottom:12px;
                padding:9px 11px;
                border:
                  1px solid rgba(59,130,246,.30);
                border-radius:9px;
                font-size:12px;
                line-height:1.45;
              "
            >
              ${htmlSafe(callbackMessage)}
            </div>
          `
          : ""
      }

      <div
        style="
          display:grid;
          grid-template-columns:
            repeat(auto-fit,minmax(145px,1fr));
          gap:10px;
        "
      >
        ${accountStatusMetric(
          "Access",
          role,
        )}

        ${accountStatusMetric(
          "Account Data Source",
          dataSource,
        )}

        ${accountStatusMetric(
          "Execution Broker",
          "TASTYTRADE",
        )}

        ${accountStatusMetric(
          "Trading",
          tradingState,
        )}
      </div>

      <div
        style="
          display:grid;
          grid-template-columns:
            repeat(auto-fit,minmax(240px,1fr));
          gap:12px;
          margin-top:14px;
        "
      >
        <section
          style="
            padding:12px;
            border:
              1px solid rgba(148,163,184,.22);
            border-radius:10px;
          "
        >
          <div
            style="
              display:flex;
              justify-content:space-between;
              align-items:flex-start;
              gap:10px;
            "
          >
            <div>
              <strong>Tastytrade</strong>

              <div
                style="
                  margin-top:3px;
                  font-size:12px;
                  opacity:.68;
                "
              >
                Execution broker
              </div>
            </div>

            <strong
              style="
                font-size:12px;
              "
            >
              ${
                tastyConnected
                  ? "CONNECTED"
                  : "SETUP REQUIRED"
              }
            </strong>
          </div>

          <div
            style="
              margin-top:11px;
              font-size:12px;
              line-height:1.5;
            "
          >
            Account:
            <strong>
              ${htmlSafe(tastyAccount)}
            </strong>
          </div>

          <div
            style="
              margin-top:10px;
            "
          >
            ${tastyDataAction}
          </div>

          ${
            !tastyConnected
              ? `
                <div
                  style="
                    margin-top:10px;
                    font-size:12px;
                    opacity:.68;
                    line-height:1.45;
                  "
                >
                  Tastytrade credentials and account
                  selection are configured from
                  Position Monitor.
                </div>
              `
              : ""
          }
        </section>

        <section
          style="
            padding:12px;
            border:
              1px solid rgba(148,163,184,.22);
            border-radius:10px;
          "
        >
          <div
            style="
              display:flex;
              justify-content:space-between;
              align-items:flex-start;
              gap:10px;
            "
          >
            <div>
              <strong>Schwab</strong>

              <div
                style="
                  margin-top:3px;
                  font-size:12px;
                  opacity:.68;
                "
              >
                Read-only account data
              </div>
            </div>

            <strong
              style="
                font-size:12px;
              "
            >
              ${
                schwabConnected
                  ? "CONNECTED"
                  : "NOT CONNECTED"
              }
            </strong>
          </div>

          <div
            style="
              margin-top:11px;
              font-size:12px;
              line-height:1.5;
            "
          >
            Selected account:
            <strong>
              ${htmlSafe(schwabAccount)}
            </strong>
          </div>

          <div
            style="
              display:flex;
              flex-wrap:wrap;
              gap:8px;
              margin-top:10px;
            "
          >
            ${schwabConnectAction}
            ${schwabDataAction}
          </div>

          ${
            (
              schwabConnected
              && !selectedSchwabAccount
            )
              ? `
                <div
                  style="
                    margin-top:10px;
                    font-size:12px;
                    opacity:.75;
                    line-height:1.45;
                  "
                >
                  Select one Schwab account before
                  using Schwab as the account data
                  source.
                </div>
              `
              : ""
          }

          ${renderSchwabAccounts(
            activeSchwabAccounts,
          )}
        </section>
      </div>

      <div
        style="
          margin-top:12px;
          padding:11px 13px;
          border:
            1px solid rgba(148,163,184,.22);
          border-radius:10px;
          font-size:13px;
          line-height:1.5;
        "
      >
        <strong>Execution:</strong>
        ${htmlSafe(executionNote)}

        <div
          style="
            margin-top:6px;
            opacity:.72;
            font-size:12px;
          "
        >
          Schwab is read-only in this phase.
          Changing the Account Data Source does not
          change where BXK submits orders.
          Execution Broker remains Tastytrade only.
        </div>
      </div>
    `;

  } catch (error) {
    console.error(
      "Account status failed:",
      error,
    );

    banner.innerHTML = `
      <div class="card-label">
        Account & Trading Status
      </div>

      <div
        style="
          margin-top:10px;
          font-size:13px;
        "
      >
        Broker status is temporarily unavailable.
        Trading permissions have not changed.
      </div>
    `;
  }
}


async function initializeAccountStatusBanner(
  authStatus,
) {
  accountStatusAuth =
    authStatus;

  if (
    !hasPrivateTradingAccess(
      authStatus,
    )
  ) {
    return;
  }

  if (!accountStatusListenerBound) {
    window.addEventListener(
      "bxk:broker-connection-changed",
      refreshAccountStatusBanner,
    );

    accountStatusListenerBound = true;
  }

  await refreshAccountStatusBanner();
}


async function initializeDashboardApplication() {
  const authStatus =
    await initializeAuthUi();

  setAccessContext(
    authStatus
  );

  positionAccessEnabled =
    applyAuthenticatedVisibility(
      authStatus
    );

  applyTradingVisibility();
  applyOwnerVisibility();

  await initializeAccountStatusBanner(
    authStatus,
  );

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
