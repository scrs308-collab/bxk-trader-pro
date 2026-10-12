// Observational audit only. No order or position endpoints belong in this module.
const ENDPOINT = "/api/stop-audit";
const COST_FIELDS = [
  ["entry_costs", "stopAuditEntryCosts"],
  ["actual_exit_costs", "stopAuditActualExitCosts"],
  ["hypothetical_exit_costs", "stopAuditHypotheticalExitCosts"],
];
let initialized = false;
let inFlight = null;
let enrolling = false;
let needsReconciliation = false;
let enabled = false;
let candidates = [];

const byId = (id) => document.getElementById(id);

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = String(text);
  return element;
}

function setText(id, text) {
  const element = byId(id);
  if (element) element.textContent = text;
}

function finiteNumber(value) {
  if (typeof value !== "number" && typeof value !== "string") return null;
  if (typeof value === "string" && !value.trim()) return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}

export function formatAuditMoney(value) {
  const amount = finiteNumber(value);
  return amount === null ? "Unavailable" : new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", minimumFractionDigits: 2,
  }).format(amount);
}

export function parseCostEstimate(value) {
  const text = String(value ?? "").trim();
  if (!/^(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$/.test(text)) {
    throw new Error("Enter all three cost estimates as nonnegative dollar amounts with at most two decimal places. Enter 0 explicitly if there is no cost.");
  }
  const amount = Number(text);
  if (!Number.isFinite(amount) || amount > 1_000_000 || !Number.isSafeInteger(Math.round(amount * 100))) {
    throw new Error("Enter a cost estimate of $1,000,000 or less.");
  }
  return amount;
}

function formatTime(value) {
  if (!value) return "Not observed";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unavailable" : parsed.toLocaleString();
}

function formatGap(value) {
  const seconds = finiteNumber(value);
  if (seconds === null || seconds < 0) return "Unavailable";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

function label(value, fallback = "Unavailable") {
  return typeof value === "string" && value.trim() ? value.replaceAll("_", " ") : fallback;
}

function settlementLabel(value) {
  if (value === "NOT_DUE") return "Not yet due";
  if (value === "UNAVAILABLE_VERIFIED_SOURCE_REQUIRED") return "Unavailable · verified source required";
  if (value === "VERIFIED") return "Verified";
  return label(value, "Pending / unavailable");
}

function statusMessage(text, isError = false) {
  const target = byId("stopAuditStatus");
  if (!target) return;
  target.textContent = text;
  target.classList.toggle("stop-audit-error", isError);
}

function formMessage(text, isError = false) {
  const target = byId("stopAuditFormMessage");
  if (!target) return;
  target.textContent = text;
  target.classList.toggle("stop-audit-error", isError);
}

function syncBusy() {
  const busy = Boolean(inFlight) || enrolling;
  const refresh = byId("stopAuditRefreshButton");
  const fields = byId("stopAuditFields");
  const section = byId("stopAuditSection");
  if (refresh) refresh.disabled = busy;
  if (fields) fields.disabled = busy || !enabled || needsReconciliation;
  if (section) section.setAttribute("aria-busy", String(busy));
  setText("stopAuditEnrollButton", enrolling ? "Enrolling…" : "Confirm stop-out and track");
}

function metric(labelText, value, { money = false, positive = false } = {}) {
  const item = node("div", "stop-audit-metric");
  item.append(node("dt", "", labelText));
  const result = node("dd", "", money ? formatAuditMoney(value) : value);
  if (positive && finiteNumber(value) !== null) {
    result.classList.add(Number(value) < 0 ? "stop-audit-negative" : "stop-audit-positive");
  }
  item.append(result);
  return item;
}

function renderAudits(audits) {
  const target = byId("stopAuditList");
  if (!target) return;
  target.replaceChildren();
  if (!audits.length) {
    target.append(node("p", "stop-audit-empty", "No stop-outs enrolled yet. Confirm an eligible closed condor below to start observing it."));
    return;
  }
  for (const audit of audits) {
    const article = node("article", "stop-audit-record");
    const header = node("div", "stop-audit-record-header");
    const heading = node("div");
    const title = node("h4", "", `${audit.underlying || "SPXW"} · ${audit.expiration || "Expiration unavailable"} · Trade #${String(audit.journal_id).slice(0, 8)}`);
    title.title = `Trade ${audit.journal_id}`;
    heading.append(title);
    heading.append(node("p", "stop-audit-subtitle", `Closed ${formatTime(audit.closed_at)} · Tracking started ${formatTime(audit.tracking_started_at)}`));
    header.append(heading, node("span", "stop-audit-badge", label(audit.status, "Status unavailable")));
    article.append(header);

    const summary = node("dl", "stop-audit-metrics");
    summary.append(
      metric("Actual net P/L", audit.actual_net_pnl, { money: true, positive: true }),
      metric("Latest hypothetical net", audit.latest_hypothetical_net_pnl, { money: true, positive: true }),
      metric("Best observed net", audit.best_hypothetical_net_pnl, { money: true, positive: true }),
      metric("Worst observed net", audit.worst_hypothetical_net_pnl, { money: true, positive: true }),
    );
    article.append(summary);

    const outcomes = node("dl", "stop-audit-facts");
    outcomes.append(
      metric("First observed breakeven", formatTime(audit.first_breakeven_at)),
      metric("First observed profit", formatTime(audit.first_profit_at)),
      metric("Expiration hypothetical net", audit.settlement_status === "VERIFIED" ? audit.expiration_hypothetical_net_pnl : null, { money: true }),
      metric("Settlement", settlementLabel(audit.settlement_status)),
    );
    article.append(outcomes);

    const valid = finiteNumber(audit.valid_samples);
    const attempted = finiteNumber(audit.attempted_samples);
    article.append(node("p", "stop-audit-coverage", `${valid ?? "?"} valid / ${attempted ?? "?"} attempted samples · Last valid observation: ${formatTime(audit.last_observed_at)}`));
    article.append(node("p", "stop-audit-coverage", `Unobserved before enrollment: ${formatGap(audit.unobserved_before_tracking_seconds)} · Current observation gap: ${formatGap(audit.current_observation_gap_seconds)} · Largest wall-clock gap: ${formatGap(audit.max_observation_gap_seconds)} (includes closed sessions and outages)`));
    if (audit.last_reason) article.append(node("p", "stop-audit-warning", `Latest sampling note: ${label(audit.last_reason)}`));

    const details = node("details", "stop-audit-details");
    details.append(node("summary", "", "Costs and observation limits"));
    const costs = node("dl", "stop-audit-facts");
    costs.append(
      metric("Actual gross P/L", audit.actual_gross_pnl, { money: true }),
      metric("Entry costs", audit.entry_costs, { money: true }),
      metric("Actual stop-close costs", audit.actual_exit_costs, { money: true }),
      metric("Hypothetical exit costs", audit.hypothetical_exit_costs, { money: true }),
      metric("Latest conservative hypothetical net", audit.latest_conservative_net_pnl, { money: true }),
      metric("Cost basis", audit.cost_basis === "USER_ESTIMATE" ? "User estimates · total USD" : "Unverified / unavailable"),
      metric("Last sampling attempt", formatTime(audit.last_attempt_at)),
      metric("Observation scope", audit.scope === "RTH_ONLY_SAMPLED_MIDPOINTS" ? "Regular session · sampled midpoints" : label(audit.scope)),
      metric("Target sampling interval", formatGap(audit.sample_interval_seconds)),
      metric("Journal trade ID", String(audit.journal_id)),
    );
    details.append(costs);
    details.append(node("p", "stop-audit-subtitle", "Actual net P/L deducts entry and actual stop-close costs. Hypothetical net P/L deducts entry and hypothetical exit costs only. Costs are user estimates. No observations are backfilled before enrollment, and missing or invalid quotes leave gaps. Observed marks do not guarantee a fill or establish what happened between samples."));
    article.append(details);
    target.append(article);
  }
}

function selectedCandidate() {
  const selected = byId("stopAuditCandidate")?.value;
  return candidates.find((candidate) => String(candidate.journal_id) === selected && candidate.eligible === true);
}

function candidateSummary() {
  const candidate = selectedCandidate();
  setText("stopAuditCandidateSummary", candidate
    ? `${candidate.underlying || "SPXW"} · Expires ${candidate.expiration || "unavailable"} · Quantity: ${candidate.quantity ?? "unavailable"} · Entry credit: ${formatAuditMoney(candidate.entry_fill_credit)} · Exit debit: ${formatAuditMoney(candidate.exit_debit)} · Recorded realized P/L: ${formatAuditMoney(candidate.realized_pnl)}. Confirm the exit reason yourself. Broker/account verification occurs on enrollment.`
    : "Select the closed trade you want to confirm as a stop-out.");
}

function resetConfirmation() {
  for (const [, id] of COST_FIELDS) {
    const input = byId(id);
    if (input) input.value = "";
  }
  const checkbox = byId("stopAuditConfirm");
  if (checkbox) checkbox.checked = false;
}

function renderCandidates(items) {
  const select = byId("stopAuditCandidate");
  const form = byId("stopAuditForm");
  if (!select || !form) return;
  const previous = select.value;
  candidates = items;
  const eligible = items.filter((candidate) => candidate.eligible === true);
  select.replaceChildren();
  const placeholder = node("option", "", "Select a closed condor…");
  placeholder.value = "";
  placeholder.disabled = true;
  select.append(placeholder);
  for (const candidate of eligible) {
    const option = node("option", "", `${candidate.underlying || "SPXW"} · ${candidate.expiration || "Expiration unavailable"} · Closed ${formatTime(candidate.closed_at)} · Trade #${String(candidate.journal_id).slice(0, 8)}`);
    option.value = String(candidate.journal_id);
    select.append(option);
  }
  const keepSelection = eligible.some((candidate) => String(candidate.journal_id) === previous);
  select.value = keepSelection ? previous : "";
  if (!keepSelection) resetConfirmation();
  form.hidden = !enabled || !eligible.length;
  const excluded = items.length - eligible.length;
  setText("stopAuditCandidateStatus", !enabled
    ? "Enrollment and sampling are disabled on this server. Existing observations remain available for review."
    : eligible.length
      ? `${eligible.length} eligible closed ${eligible.length === 1 ? "condor" : "condors"} awaiting your stop-out confirmation.${excluded ? ` ${excluded} other closed ${excluded === 1 ? "trade is" : "trades are"} not eligible.` : ""}`
      : "No eligible closed condors are available. Enrollment requires an account-verified Tastytrade SPXW PM-settled condor that has not already been enrolled.");
  candidateSummary();
}

async function requestJson(options = {}) {
  const response = await fetch(ENDPOINT, {
    cache: "no-store",
    credentials: "same-origin",
    signal: AbortSignal.timeout(20_000),
    ...options,
    headers: { "Accept": "application/json", ...(options.headers || {}) },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`The server returned an unreadable response (HTTP ${response.status}).`);
  }
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (HTTP ${response.status}).`;
    throw new Error(detail);
  }
  return data;
}

function initializeControls() {
  if (initialized) return;
  const form = byId("stopAuditForm");
  if (!form) return;
  initialized = true;
  byId("stopAuditRefreshButton")?.addEventListener("click", () => loadStopAudit());
  byId("stopAuditCandidate")?.addEventListener("change", () => {
    resetConfirmation();
    formMessage("");
    candidateSummary();
  });
  form.addEventListener("submit", enroll);
}

async function enroll(event) {
  event.preventDefault();
  if (enrolling || inFlight || !enabled || needsReconciliation) return;
  const form = byId("stopAuditForm");
  if (typeof form?.reportValidity === "function" && !form.reportValidity()) return;
  const candidate = selectedCandidate();
  if (!candidate || !byId("stopAuditConfirm")?.checked) {
    formMessage("Select an eligible closed trade and confirm that your stop was hit before enrolling.", true);
    return;
  }
  const payload = { journal_id: candidate.journal_id, confirm_stop_out: true };
  try {
    for (const [name, id] of COST_FIELDS) payload[name] = parseCostEstimate(byId(id)?.value);
  } catch (error) {
    formMessage(error.message, true);
    return;
  }
  enrolling = true;
  syncBusy();
  formMessage("Confirming enrollment…");
  let saved = false;
  let failure = "";
  try {
    await requestJson({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    saved = true;
    resetConfirmation();
    formMessage("Stop-out enrolled. Observation starts from enrollment; the historical gap remains unobserved.");
  } catch (error) {
    failure = error.message;
    formMessage(`Could not confirm enrollment: ${error.message} Checking the latest audit list before another attempt.`, true);
  } finally {
    // A failed response may follow a successful write. Reconcile before permitting a retry.
    needsReconciliation = true;
    const refreshed = await loadAuditList();
    if (!refreshed) {
      formMessage(saved
        ? "Enrollment succeeded, but the latest list could not be loaded. Refresh to see the audit."
        : "Enrollment status is uncertain. Refresh successfully before trying again; the request may already have been saved.", !saved);
    } else if (!saved) {
      const persisted = refreshed.audits.some((audit) => String(audit.journal_id) === String(payload.journal_id));
      if (persisted) formMessage("The latest list confirms this stop-out is enrolled. Observation starts from enrollment; the historical gap remains unobserved.");
      else formMessage(`Enrollment was not confirmed: ${failure} The list is refreshed; review the trade and costs before trying again.`, true);
    }
    enrolling = false;
    syncBusy();
  }
}

export function loadStopAudit() {
  // Tab re-entry during a write must not start a read that predates that write.
  if (enrolling) return inFlight || Promise.resolve(null);
  return loadAuditList();
}

function loadAuditList() {
  if (!byId("stopAuditSection")) return Promise.resolve(null);
  initializeControls();
  if (inFlight) return inFlight;
  statusMessage("Loading Stop Audit…");
  // Defer the read so inFlight is set before any completion handler runs.
  inFlight = Promise.resolve().then(async () => {
    try {
      const data = await requestJson();
      if (typeof data?.enabled !== "boolean" || !Array.isArray(data.audits) || !Array.isArray(data.candidates)
        || data.audits.some((item) => !item || typeof item !== "object")
        || data.candidates.some((item) => !item || typeof item !== "object")) {
        throw new Error("The server returned an incomplete Stop Audit response.");
      }
      enabled = data.enabled;
      if (needsReconciliation && !enrolling) formMessage("Audit list refreshed. Check the tracked stop-outs before trying enrollment again.");
      needsReconciliation = false;
      renderAudits(data.audits);
      renderCandidates(data.candidates);
      statusMessage(`${enabled ? "Observational tracking enabled" : "Tracking disabled"} · Updated ${new Date().toLocaleTimeString()}`);
      return data;
    } catch (error) {
      // Keep prior observations visible, but never enroll against a failed eligibility check.
      enabled = false;
      statusMessage(`Stop Audit unavailable: ${error.message} Any displayed observations may be out of date.`, true);
      setText("stopAuditCandidateStatus", "Eligibility could not be verified. Refresh successfully before enrolling a trade.");
      return null;
    } finally {
      inFlight = null;
      syncBusy();
    }
  });
  syncBusy();
  return inFlight;
}
