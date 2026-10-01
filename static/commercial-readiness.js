const READINESS_URL = "/api/admin/commercial-readiness";
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

function flag(label, value) {
  const ready = value === true;
  return '<div style="display:flex;justify-content:space-between;gap:12px;' +
    'padding:8px 0;border-bottom:1px solid rgba(148,163,184,.12);">' +
    '<span>' + escapeHtml(label) + '</span>' +
    '<strong style="font-size:11px;">' +
    (ready ? "READY" : "NOT READY") +
    '</strong></div>';
}

async function loadCommercialReadiness() {
  const panel = byId("commercialReadinessPanel");
  if (!panel) return;

  panel.innerHTML = "Checking...";

  try {
    const response = await fetch(
      READINESS_URL + "?_=" + Date.now(),
      {cache: "no-store"}
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Commercial readiness check failed."
      );
    }

    const checks = data.checks || {};

    panel.innerHTML =
      '<div style="margin-bottom:10px;font-size:13px;opacity:.75;">' +
      escapeHtml(data.ready_count) + ' of ' +
      escapeHtml(data.check_count) +
      ' automated readiness checks currently pass.</div>' +
      flag("Authentication", checks.authentication_ready) +
      flag("Database", checks.database_ready) +
      flag("Broker secret storage", checks.broker_secret_storage_ready) +
      flag("Schwab OAuth config", checks.schwab_oauth_configured) +
      flag("Stripe checkout config", checks.stripe_checkout_configured) +
      flag("Reviewer safe mode", checks.reviewer_safe_mode) +
      flag("Production demo hidden", checks.production_demo_hidden) +
      flag("Operational email", checks.operational_email_ready) +
      '<div style="margin-top:10px;font-size:12px;line-height:1.45;opacity:.72;">' +
      'Schwab commercial approval is tracked separately because it is an external approval, not a software configuration check.' +
      '</div>';
  } catch (error) {
    console.error(
      "Commercial readiness failed:",
      error
    );
    panel.textContent = error.message;
  }
}

export function initializeCommercialReadiness() {
  if (initialized) return;

  const card = byId("commercialReadinessCard");
  if (!card) return;

  initialized = true;
  card.hidden = false;

  const refresh =
    byId("refreshCommercialReadiness");

  if (refresh) {
    refresh.addEventListener(
      "click",
      loadCommercialReadiness
    );
  }

  loadCommercialReadiness();
}
