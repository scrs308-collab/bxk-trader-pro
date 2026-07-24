console.log("BXK Trader Pro Dashboard - V10");

import {
  API_URL,
  DASHBOARD_REFRESH_MS,
  STALE_AFTER_MS,
  OFFLINE_AFTER_MS,
} from "./config.js";

import {
  el,
  setText,
  nowTime,
} from "./utils.js";

import {
  updateDashboard,
} from "./market.js";

import {
  updateChecklist,
} from "./checklist.js";

import {
  loadBestTrade,
} from "./best-trade.js";

import {
  loadPositions,
} from "./position.js";

let lastSuccessfulUpdate = null;
let dashboardRefreshInProgress = false;
let dashboardRefreshTimer = null;

function setApiStatus(status) {
  const apiStatus = el("apiStatus");

  if (!apiStatus) {
    return;
  }

  if (status === "live") {
    apiStatus.textContent = "● LIVE";
    apiStatus.className = "status-pill online";
    return;
  }

  if (status === "stale") {
    apiStatus.textContent = "● STALE";
    apiStatus.className = "status-pill stale";
    return;
  }

  apiStatus.textContent = "● OFFLINE";
  apiStatus.className = "status-pill offline";
}

function updateApiFreshness() {
  if (!lastSuccessfulUpdate) {
    setApiStatus("offline");
    return;
  }

  const age =
    Date.now() - lastSuccessfulUpdate;

  if (age >= OFFLINE_AFTER_MS) {
    setApiStatus("offline");
    return;
  }

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
    setApiStatus("live");
  } catch (error) {
    console.error(
      "Dashboard fetch failed:",
      error,
    );

    setApiStatus("offline");
    setText(
      "recommendation",
      "API Offline",
    );
  }
}

function updateClock() {
  setText("clock", nowTime());
}

async function refreshDashboard() {
  if (dashboardRefreshInProgress) {
    return;
  }

  dashboardRefreshInProgress = true;

  try {
    await Promise.allSettled([
      fetchRecommendation(),
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

initializeDashboardTabs();