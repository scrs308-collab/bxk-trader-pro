const ACCESS_URL = "/api/access-requests";
const SUPPORT_URL = "/api/support-requests";
let initialized = false;

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function requestJson(url, options) {
  const response = await fetch(url, {
    cache: "no-store",
    ...(options || {}),
    headers: {
      "Content-Type": "application/json",
      ...((options && options.headers) || {}),
    },
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail || "Request failed (" + response.status + ")."
    );
  }

  return data;
}

function formatDate(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}

function actionButton(type, id, label, status) {
  return '<button type="button" ' +
    'data-request-type="' + escapeHtml(type) + '" ' +
    'data-request-id="' + escapeHtml(id) + '" ' +
    'data-request-status="' + escapeHtml(status) + '" ' +
    'style="padding:7px 10px;border-radius:7px;' +
    'border:1px solid rgba(148,163,184,.25);' +
    'background:rgba(15,23,42,.85);color:inherit;' +
    'cursor:pointer;font-size:11px;font-weight:700;">' +
    escapeHtml(label) +
    '</button>';
}

function renderAccess(items) {
  const container = byId("bxkAccessRequestsList");
  if (!container) return;

  if (!Array.isArray(items) || !items.length) {
    container.innerHTML = "<div>No access requests found.</div>";
    return;
  }

  container.innerHTML = items.map(function(item) {
    const intended = item.intended_use
      ? '<div style="margin-top:6px;"><strong>Use:</strong> ' +
        escapeHtml(item.intended_use) + '</div>'
      : "";

    return '<article style="border:1px solid rgba(148,163,184,.2);' +
      'border-radius:10px;padding:12px;margin-top:10px;">' +
      '<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;">' +
      '<div><strong>' + escapeHtml(item.full_name) + '</strong>' +
      '<div style="opacity:.75;font-size:12px;">' + escapeHtml(item.email) + '</div></div>' +
      '<div style="font-size:11px;font-weight:800;">' + escapeHtml(item.status) + '</div></div>' +
      '<div style="margin-top:8px;font-size:12px;line-height:1.45;">' +
      '<div><strong>Broker:</strong> ' + escapeHtml(item.broker || "--") + '</div>' +
      '<div><strong>Submitted:</strong> ' + escapeHtml(formatDate(item.created_at)) + '</div>' +
      intended + '</div>' +
      '<div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:10px;">' +
      actionButton("access", item.id, "Approve", "APPROVED") +
      actionButton("access", item.id, "Decline", "DECLINED") +
      actionButton("access", item.id, "Close", "CLOSED") +
      '<button type="button" data-prepare-user-from-access="true" ' +
      'data-access-name="' + escapeHtml(item.full_name) + '" ' +
      'data-access-email="' + escapeHtml(item.email) + '" ' +
      'style="padding:7px 10px;border-radius:7px;' +
      'border:1px solid rgba(59,130,246,.4);' +
      'background:rgba(37,99,235,.18);color:inherit;' +
      'cursor:pointer;font-size:11px;font-weight:700;">' +
      'Prepare User' +
      '</button>' +
      '</div></article>';
  }).join("");
}

function renderSupport(items) {
  const container = byId("bxkSupportRequestsList");
  if (!container) return;

  if (!Array.isArray(items) || !items.length) {
    container.innerHTML = "<div>No support requests found.</div>";
    return;
  }

  container.innerHTML = items.map(function(item) {
    return '<article style="border:1px solid rgba(148,163,184,.2);' +
      'border-radius:10px;padding:12px;margin-top:10px;">' +
      '<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;">' +
      '<div><strong>' + escapeHtml(item.subject) + '</strong>' +
      '<div style="opacity:.75;font-size:12px;">' +
      escapeHtml(item.name) + ' · ' + escapeHtml(item.email) + '</div></div>' +
      '<div style="font-size:11px;font-weight:800;">' + escapeHtml(item.status) + '</div></div>' +
      '<div style="margin-top:8px;font-size:12px;line-height:1.45;">' +
      '<div><strong>Submitted:</strong> ' + escapeHtml(formatDate(item.created_at)) + '</div>' +
      '<div style="margin-top:6px;">' + escapeHtml(item.message) + '</div></div>' +
      '<div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:10px;">' +
      actionButton("support", item.id, "Resolve", "RESOLVED") +
      actionButton("support", item.id, "Close", "CLOSED") +
      '</div></article>';
  }).join("");
}

async function loadRequests() {
  const message = byId("bxkAdminRequestsMessage");

  try {
    const results = await Promise.all([
      requestJson(ACCESS_URL + "?_=" + Date.now()),
      requestJson(SUPPORT_URL + "?_=" + Date.now()),
    ]);

    renderAccess(results[0].requests);
    renderSupport(results[1].requests);

    if (message) message.textContent = "Requests loaded.";
  } catch (error) {
    console.error("Admin requests load failed:", error);
    if (message) message.textContent = error.message;
  }
}

async function updateRequest(type, id, status) {
  const base = type === "access" ? ACCESS_URL : SUPPORT_URL;

  await requestJson(
    base + "/" + encodeURIComponent(id) + "/status",
    {
      method: "PATCH",
      body: JSON.stringify({status: status}),
    }
  );

  await loadRequests();
}

export function initializeAdminRequests() {
  if (initialized) return;

  const card = byId("adminRequestsCard");
  if (!card) return;

  initialized = true;
  card.hidden = false;

  card.addEventListener("click", async function(event) {
    const prepare =
      event.target.closest(
        "button[data-prepare-user-from-access]"
      );

    if (prepare) {
      const email =
        prepare.dataset.accessEmail || "";
      const name =
        prepare.dataset.accessName || "";

      const suggestedUsername =
        name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, ".")
          .replace(/^\.+|\.+$/g, "")
          .slice(0, 100);

      const usernameField =
        byId("bxkAdminUsername");
      const emailField =
        byId("bxkAdminEmail");
      const roleField =
        byId("bxkAdminRole");

      if (usernameField) {
        usernameField.value =
          suggestedUsername;
      }

      if (emailField) {
        emailField.value = email;
      }

      if (roleField) {
        roleField.value = "BETA";
      }

      const message =
        byId("bxkAdminRequestsMessage");

      if (message) {
        message.textContent =
          "User Administration prefilled. Review the username, generate a temporary password, then create the user.";
      }

      const adminCard =
        byId("adminUsersCard");

      if (adminCard) {
        adminCard.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }

      return;
    }

    const button = event.target.closest("button[data-request-type]");
    if (!button) return;

    button.disabled = true;

    try {
      await updateRequest(
        button.dataset.requestType,
        button.dataset.requestId,
        button.dataset.requestStatus
      );
    } catch (error) {
      console.error("Request status update failed:", error);
      button.disabled = false;
      const message = byId("bxkAdminRequestsMessage");
      if (message) message.textContent = error.message;
    }
  });

  const refresh = byId("bxkRefreshAdminRequests");
  if (refresh) {
    refresh.addEventListener("click", loadRequests);
  }

  loadRequests();
}
