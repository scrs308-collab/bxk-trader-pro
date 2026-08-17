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
} from "./best-trade.js?v=11";

import {
  loadPositions,
} from "./position.js";

let lastSuccessfulUpdate = null;
let consecutiveNetworkFailures = 0;
let backendOffline = false;
let dashboardRefreshInProgress = false;
let dashboardRefreshTimer = null;

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

    updateDashboard(
      data,
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

async function fetchLiveMarketSummary() {
  try {
    const response = await fetch(
      `/api/live-market?_=${Date.now()}`,
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
