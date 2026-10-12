import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Minimal DOM with deliberately no HTML parsing: any innerHTML use fails the test.
class Element {
  constructor(tag = "div") {
    this.tagName = tag;
    this.children = [];
    this.listeners = {};
    this.attributes = {};
    this.value = "";
    this.checked = false;
    this.hidden = false;
    this.disabled = false;
    this.classes = new Set();
    this.classList = {
      add: (...values) => values.forEach((value) => this.classes.add(value)),
      toggle: (value, on) => on ? this.classes.add(value) : this.classes.delete(value),
    };
  }
  set innerHTML(_) { throw new Error("Unsafe HTML rendering is prohibited."); }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text || this.children.map((child) => child.textContent).join(" "); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.text = ""; this.children = items; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  reportValidity() { return true; }
}

const elements = new Map();
for (const id of [
  "stopAuditSection", "stopAuditStatus", "stopAuditRefreshButton", "stopAuditList",
  "stopAuditCandidateStatus", "stopAuditForm", "stopAuditFields", "stopAuditCandidate",
  "stopAuditCandidateSummary", "stopAuditEntryCosts", "stopAuditActualExitCosts",
  "stopAuditHypotheticalExitCosts", "stopAuditConfirm", "stopAuditEnrollButton", "stopAuditFormMessage",
]) elements.set(id, new Element());
globalThis.document = {
  getElementById: (id) => elements.get(id),
  createElement: (tag) => new Element(tag),
};
const byId = (id) => elements.get(id);
const source = readFileSync("static/stop-audit.js", "utf8");
const { loadStopAudit, parseCostEstimate, formatAuditMoney } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);

for (const value of [null, undefined, "", " ", "-1", "1.001", "NaN", "Infinity", "1e2", "0x10", "1000000.01", true]) {
  assert.throws(() => parseCostEstimate(value));
}
assert.equal(parseCostEstimate("0"), 0, "Zero must be an explicit estimate.");
assert.equal(parseCostEstimate("12.34"), 12.34);
assert.equal(parseCostEstimate(".50"), 0.5);
assert.equal(parseCostEstimate(" 4.20 "), 4.2);
for (const value of [null, undefined, "", " ", false, [], {}, "NaN"]) {
  assert.equal(formatAuditMoney(value), "Unavailable", "Missing data must never become zero.");
}
assert.equal(formatAuditMoney(0), "$0.00");
assert.equal(formatAuditMoney(-123.45), "-$123.45");

const candidate = { journal_id: 8, underlying: "SPXW", expiration: "2026-10-16", closed_at: "2026-10-12T14:00:00Z", eligible: true, quantity: 2, realized_pnl: -200, entry_fill_credit: 2.5, exit_debit: 3.5 };
const audit = {
  journal_id: 7, underlying: "<img src=x onerror=alert(1)>", expiration: "2026-10-16", status: "TRACKING",
  cost_basis: "USER_ESTIMATE", actual_net_pnl: -210, latest_hypothetical_net_pnl: null,
  expiration_hypothetical_net_pnl: 0, settlement_status: "PENDING", valid_samples: 0, attempted_samples: 1,
  last_reason: "<script>untrusted</script>",
};
let data = { enabled: true, audits: [audit], candidates: [candidate, { journal_id: 9, eligible: false, reason: "UNVERIFIED" }] };
let calls = [];
let handleFetch = async () => ({ ok: true, status: 200, json: async () => data });
globalThis.fetch = async (url, options) => {
  calls.push({ url, options });
  assert.equal(url, "/api/stop-audit", "No position or order endpoint may be used.");
  return handleFetch(url, options);
};

const first = loadStopAudit();
const repeated = loadStopAudit();
assert.equal(first, repeated, "Repeated loads must share the same request.");
assert.equal(byId("stopAuditRefreshButton").disabled, true);
await first;
assert.equal(calls.length, 1);
assert.equal(byId("stopAuditRefreshButton").disabled, false);
assert.equal(byId("stopAuditFields").disabled, false);
assert.equal(byId("stopAuditForm").hidden, false);
assert.match(byId("stopAuditList").textContent, /<img src=x onerror=alert\(1\)>/);
assert.match(byId("stopAuditList").textContent, /<script>untrusted<\/script>/);
assert.match(byId("stopAuditList").textContent, /Expiration hypothetical net Unavailable/);
assert.equal(byId("stopAuditCandidate").children.length, 2, "Only eligible trades can be selected.");
assert.equal(byId("stopAuditCandidate").value, "", "No trade should be silently preselected.");
assert.match(byId("stopAuditCandidateStatus").textContent, /awaiting your stop-out confirmation/);

const submit = () => byId("stopAuditForm").listeners.submit({ preventDefault() {} });
const fill = () => {
  byId("stopAuditCandidate").value = "8";
  byId("stopAuditConfirm").checked = true;
  byId("stopAuditEntryCosts").value = "1.50";
  byId("stopAuditActualExitCosts").value = "2.00";
  byId("stopAuditHypotheticalExitCosts").value = "0";
};
fill();
byId("stopAuditConfirm").checked = false;
await submit();
assert.equal(calls.length, 1, "No enrollment without explicit stop-out confirmation.");
byId("stopAuditConfirm").checked = true;
byId("stopAuditHypotheticalExitCosts").value = "";
await submit();
assert.equal(calls.length, 1, "No missing-cost fallback to zero.");
fill();
byId("stopAuditCandidate").listeners.change();
assert.equal(byId("stopAuditConfirm").checked, false, "Changing trade resets its confirmation.");
assert.equal(byId("stopAuditEntryCosts").value, "", "Costs must not leak from a different trade.");

fill();
let resolvePost;
handleFetch = async (_url, options) => {
  if (options.method === "POST") {
    await new Promise((resolve) => { resolvePost = resolve; });
    data = { enabled: true, audits: [audit, { ...audit, journal_id: 8 }], candidates: [] };
    return { ok: true, status: 200, json: async () => ({ id: 1 }) };
  }
  return { ok: true, status: 200, json: async () => data };
};
const enrolling = submit();
await submit();
const callsWhileEnrolling = calls.length;
await loadStopAudit();
assert.equal(calls.length, callsWhileEnrolling, "Tab re-entry must not read a stale list during enrollment.");
assert.equal(calls.filter((call) => call.options.method === "POST").length, 1, "Double submits must not duplicate enrollment.");
assert.equal(byId("stopAuditFields").disabled, true);
assert.equal(byId("stopAuditRefreshButton").disabled, true);
assert.deepEqual(JSON.parse(calls.at(-1).options.body), { journal_id: 8, confirm_stop_out: true, entry_costs: 1.5, actual_exit_costs: 2, hypothetical_exit_costs: 0 });
resolvePost();
await enrolling;
assert.equal(byId("stopAuditForm").hidden, true);
assert.match(byId("stopAuditFormMessage").textContent, /Stop-out enrolled/);
assert.equal(calls.at(-1).options.method, undefined, "Every write is followed by a fresh list read.");

data = { enabled: true, audits: [], candidates: [candidate] };
handleFetch = async () => ({ ok: true, status: 200, json: async () => data });
await loadStopAudit();
fill();
handleFetch = async () => { throw new Error("Disconnected"); };
await submit();
assert.equal(byId("stopAuditFields").disabled, true);
assert.match(byId("stopAuditFormMessage").textContent, /status is uncertain/);
const uncertainCalls = calls.length;
await submit();
assert.equal(calls.length, uncertainCalls, "An uncertain write cannot be retried before reconciliation.");
handleFetch = async () => ({ ok: true, status: 200, json: async () => data });
await loadStopAudit();
assert.equal(byId("stopAuditFields").disabled, false);

// The server can save a write and lose its response. The next GET confirms it.
fill();
handleFetch = async (_url, options) => {
  if (options.method === "POST") {
    data = { enabled: true, audits: [{ ...audit, journal_id: 8 }], candidates: [] };
    throw new Error("Response interrupted");
  }
  return { ok: true, status: 200, json: async () => data };
};
await submit();
assert.match(byId("stopAuditFormMessage").textContent, /confirms this stop-out is enrolled/);
assert.equal(byId("stopAuditForm").hidden, true);

data = { enabled: false, audits: [], candidates: [candidate] };
await loadStopAudit();
assert.equal(byId("stopAuditForm").hidden, true);
assert.equal(byId("stopAuditFields").disabled, true);
assert.match(byId("stopAuditCandidateStatus").textContent, /disabled/);
data = { enabled: true, audits: [] }; // Malformed responses fail closed.
await loadStopAudit();
assert.match(byId("stopAuditStatus").textContent, /incomplete/);
assert.equal(byId("stopAuditFields").disabled, true);
data = { enabled: true, audits: [{ ...audit, settlement_status: "VERIFIED" }], candidates: [] };
await loadStopAudit();
assert.match(byId("stopAuditList").textContent, /Expiration hypothetical net \$0.00/, "Only a verified settlement can show a real zero.");
console.log("Stop Audit UI: validation, safe rendering, missing data, eligibility, loading, duplicate prevention, and uncertain-write reconciliation passed.");
