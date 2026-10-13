import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

class Element {
  constructor() {
    this.listeners = {};
    this.dataset = {};
    this.value = "";
    this.textContent = "";
    this.className = "";
    this.hidden = false;
    this.disabled = false;
    this.innerHTML = "";
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  focus() { this.focused = true; }
  scrollIntoView() {}
  querySelectorAll(selector) {
    const attribute = selector.match(/^button\[(data-[\w-]+)\]$/)?.[1];
    if (!attribute) return [];
    return [...this.innerHTML.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)]
      .filter(([, attributes]) => attributes.includes(attribute + "="))
      .map(([, attributes, label]) => {
        const button = new Element();
        for (const [, name, value] of attributes.matchAll(/data-([\w-]+)="([^"]*)"/g)) {
          const key = name.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
          button.dataset[key] = value;
        }
        button.disabled = /\bdisabled\b/.test(attributes);
        button.textContent = label.trim();
        return button;
      });
  }
}

function elementsFor(ids) {
  const elements = Object.fromEntries(ids.map((id) => [id, new Element()]));
  return { elements, document: { getElementById: (id) => elements[id] } };
}

const adminSource = readFileSync("static/admin-users.js", "utf8");
const admin = elementsFor([
  "bxkAdminUsersList", "bxkAdminUsersMessage", "bxkAdminUsername", "bxkAdminEmail",
  "bxkAdminRole", "bxkAdminTemporaryPassword", "bxkCreateUserButton",
]);
let requests = [];
let confirmations = [];
let confirmAllowed = true;
let fetchHandler;
const sandbox = {
  document: admin.document,
  window: { confirm: (message) => { confirmations.push(message); return confirmAllowed; } },
  console,
  fetch: async (url, options = {}) => {
    requests.push({ url, options });
    return fetchHandler(url, options);
  },
};
vm.createContext(sandbox);
vm.runInContext(adminSource.replace(/^export /gm, ""), sandbox);
const response = (data, ok = true, status = ok ? 200 : 400) => ({ ok, status, json: async () => data });
const user = {
  id: 12, username: "test.viewer", email: "viewer@example.test", role: "VIEWER",
  is_active: true, must_change_password: true, setup_invitation_eligible: true,
};
const statusData = (status) => ({
  invitation: { status, created_at: "2026-10-13T19:00:00Z", expires_at: "2099-10-14T19:00:00Z" },
  user: { ...user, setup_invitation: { status, created_at: "2026-10-13T19:00:00Z", expires_at: "2099-10-14T19:00:00Z" } },
});

// The server eligibility flag is necessary, but never overrides protected local attributes.
for (const override of [
  { setup_invitation_eligible: false }, { setup_invitation_eligible: undefined },
  { role: "OWNER" }, { is_active: false }, { must_change_password: false },
]) {
  sandbox.renderUsers([{ ...user, ...override }]);
  assert.doesNotMatch(admin.elements.bxkAdminUsersList.innerHTML, /data-invitation-user-id/);
  await sandbox.sendSetupInvitation("12");
}
assert.equal(requests.length, 0);
assert.equal(confirmations.length, 0);
sandbox.renderUsers([user]);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /SEND SETUP LINK/);
confirmAllowed = false;
await sandbox.sendSetupInvitation("12");
assert.equal(requests.length, 0, "Cancel must not send an email.");
assert.match(confirmations[0], /Username: test.viewer/);
assert.match(confirmations[0], /Email: viewer@example.test/);
confirmAllowed = true;

let resolveSend;
fetchHandler = async () => new Promise((resolve) => { resolveSend = resolve; });
const sending = sandbox.sendSetupInvitation("12");
await sandbox.sendSetupInvitation("12");
assert.equal(requests.length, 1, "Repeated clicks cannot send duplicate messages.");
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /disabled[\s\S]*?SENDING SETUP LINK/);
// A concurrent list redraw cannot reset the in-flight guard.
sandbox.renderUsers([user]);
await sandbox.sendSetupInvitation("12");
assert.equal(requests.length, 1);
assert.equal(requests[0].url, "/api/admin/users/12/setup-invitation");
assert.equal(requests[0].options.method, "POST");
assert.deepEqual(JSON.parse(requests[0].options.body), {
  expected_email: user.email, expected_username: user.username,
}, "The backend must verify the exact account reviewed; no temporary password is mailed.");
resolveSend(response(statusData("ACCEPTED")));
await sending;
assert.match(admin.elements.bxkAdminUsersMessage.textContent, /accepted by the mail provider/);
assert.match(admin.elements.bxkAdminUsersMessage.textContent, /Delivery is not confirmed/);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /ACCEPTED BY PROVIDER/);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /Requested:/);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /Link expires:/);

// A delayed refresh from before a send cannot erase its new outcome or eligibility.
let resolveOldList;
fetchHandler = async (_url, options) => options.method === "POST"
  ? response(statusData("ACCEPTED"))
  : new Promise((resolve) => { resolveOldList = resolve; });
const oldRead = sandbox.loadUsers();
await sandbox.sendSetupInvitation("12");
resolveOldList(response({ users: [user] }));
assert.equal(await oldRead, false);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /ACCEPTED BY PROVIDER/);

fetchHandler = async () => response(statusData("FAILED"));
await sandbox.sendSetupInvitation("12");
assert.match(confirmations.at(-1), /replaces any previous setup link/);
assert.match(admin.elements.bxkAdminUsersMessage.textContent, /failed/);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /SETUP EMAIL: FAILED/);
fetchHandler = async () => response(statusData("UNKNOWN"));
await sandbox.sendSetupInvitation("12");
assert.match(admin.elements.bxkAdminUsersMessage.textContent, /unknown/);
assert.match(admin.elements.bxkAdminUsersMessage.textContent, /may have been sent/);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /SUBMISSION STATUS UNKNOWN/);

// Rejected/cooldown requests surface actionable safe text and refresh without another send.
for (const [code, detail] of [
  [422, "The account changed since it was reviewed. Refresh and confirm its username and email again."],
  [429, "Wait at least 60 seconds before requesting another setup email."],
]) {
  const before = requests.length;
  fetchHandler = async (_url, options) => options.method === "POST"
    ? response({ detail }, false, code)
    : response({ users: [user] });
  await sandbox.sendSetupInvitation("12");
  assert.equal(requests.length - before, 2);
  assert.equal(admin.elements.bxkAdminUsersMessage.textContent, `Setup email request was rejected. ${detail}`);
}

// Network uncertainty never triggers an automatic second send. Failed reconciliation locks retries.
fetchHandler = async () => { throw new Error("Network interrupted"); };
const beforeNetworkFailure = requests.length;
await sandbox.sendSetupInvitation("12");
assert.equal(requests.length - beforeNetworkFailure, 2, "One POST plus one read-only reconciliation.");
assert.equal(requests.at(-1).options.method, undefined);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /REFRESH USERS BEFORE RETRY/);
await sandbox.sendSetupInvitation("12");
assert.equal(requests.length - beforeNetworkFailure, 2);
fetchHandler = async () => response({ users: [statusData("ACCEPTED").user] });
await sandbox.loadUsers();
assert.doesNotMatch(admin.elements.bxkAdminUsersList.innerHTML, /REFRESH USERS BEFORE RETRY/);

// A lost successful POST is reconciled as an accepted provider submission.
fetchHandler = async (_url, options) => {
  if (options.method === "POST") throw new Error("Response lost");
  return response({ users: [statusData("ACCEPTED").user] });
};
const beforeLostResponse = requests.length;
await sandbox.sendSetupInvitation("12");
assert.equal(requests.length - beforeLostResponse, 2);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /ACCEPTED BY PROVIDER/);
assert.match(admin.elements.bxkAdminUsersMessage.textContent, /may have been sent/);

// Untrusted user metadata cannot introduce HTML in the invitation metadata or identity.
sandbox.renderUsers([{ ...user, username: '<img src=x onerror="alert(1)">', email: "<svg>" }]);
assert.doesNotMatch(admin.elements.bxkAdminUsersList.innerHTML, /<img|<svg/);
assert.match(admin.elements.bxkAdminUsersList.innerHTML, /&lt;img/);

// Creation remains separate: creates a user and refreshes, never sends an invitation.
Object.assign(admin.elements.bxkAdminUsername, { value: user.username });
Object.assign(admin.elements.bxkAdminEmail, { value: user.email });
Object.assign(admin.elements.bxkAdminRole, { value: "VIEWER" });
Object.assign(admin.elements.bxkAdminTemporaryPassword, { value: "Mock-only-password-123" });
let resolveCreate;
fetchHandler = async (_url, options) => {
  if (options.method === "POST") return new Promise((resolve) => { resolveCreate = resolve; });
  return response({ users: [user] });
};
const beforeCreate = requests.length;
const creating = sandbox.createUser();
await sandbox.createUser();
assert.equal(requests.length - beforeCreate, 1);
resolveCreate(response({ user }));
await creating;
assert.equal(requests.length - beforeCreate, 2);
assert.ok(requests.slice(beforeCreate).every(({ url }) => !url.includes("setup-invitation")));
assert.equal(admin.elements.bxkAdminTemporaryPassword.value, "");
assert.match(admin.elements.bxkAdminUsersMessage.textContent, /No email has been sent/);

// Approve and Prepare User never create accounts or send invitations as a side effect.
const requestElements = elementsFor([
  "adminRequestsCard", "bxkAdminRequestsMessage", "bxkAccessRequestsList", "bxkSupportRequestsList",
  "bxkAdminUsername", "bxkAdminEmail", "bxkAdminRole", "bxkAdminTemporaryPassword", "adminUsersCard",
]);
const requestCalls = [];
const requestSandbox = {
  document: requestElements.document, console,
  fetch: async (url, options) => {
    requestCalls.push({ url, options });
    return response({ requests: [] });
  },
};
vm.createContext(requestSandbox);
vm.runInContext(readFileSync("static/admin-requests.js", "utf8").replace(/^export /gm, ""), requestSandbox);
await requestSandbox.updateRequest("access", "access-test", "APPROVED");
assert.equal(requestCalls.length, 3);
assert.ok(requestCalls.every(({ url }) => url.startsWith("/api/access-requests") || url.startsWith("/api/support-requests")));
assert.equal(requestCalls[0].options.method, "PATCH");
assert.match(requestElements.elements.bxkAdminRequestsMessage.textContent, /No account was created and no setup link was sent/);
requestSandbox.initializeAdminRequests();
const beforePrepare = requestCalls.length;
requestElements.elements.bxkAdminTemporaryPassword.value = "Previously-entered-password";
await requestElements.elements.adminRequestsCard.listeners.click({
  target: { closest: (selector) => selector === "button[data-prepare-user-from-access]"
    ? { dataset: { accessEmail: "new.person@example.test", accessName: "New Person" } }
    : null },
});
assert.equal(requestCalls.length, beforePrepare);
assert.equal(requestElements.elements.bxkAdminUsername.value, "new.person");
assert.equal(requestElements.elements.bxkAdminEmail.value, "new.person@example.test");
assert.equal(requestElements.elements.bxkAdminTemporaryPassword.value, "");

const html = readFileSync("static/setup-password.html", "utf8");
const pageSource = html.match(/<script>([\s\S]*?)<\/script>/)[1];
assert.doesNotMatch(html, /<script[^>]+src=|<link[^>]+href=["']https?:|<img[^>]+src=["']https?:/i);
assert.match(html, /name="referrer" content="no-referrer"/);
assert.match(html, /id="newPassword" type="password"/);
assert.match(html, /id="confirmPassword" type="password"/);
assert.doesNotMatch(pageSource, /localStorage|sessionStorage|console\.|location\.search/);

function page({ hash = "#token=mock-token-for-local-tests", search = "", replaceFails = false } = {}) {
  const state = elementsFor(["setupPasswordForm", "setupButton", "newPassword", "confirmPassword", "status", "loginLink"]);
  state.elements.setupPasswordForm.hidden = true;
  state.calls = [];
  state.replacements = [];
  state.events = {};
  state.fetchHandler = async () => response({ password_set: true });
  const location = { hash, search, pathname: "/setup-password" };
  const context = {
    document: state.document,
    URLSearchParams,
    window: {
      location,
      history: { replaceState: (...args) => {
        if (replaceFails) throw new Error("Unable to clean URL");
        state.replacements.push(args);
        location.hash = "";
        location.search = "";
      } },
      addEventListener: (name, callback) => { state.events[name] = callback; },
    },
    fetch: async (url, options) => { state.calls.push({ url, options }); return state.fetchHandler(url, options); },
    console: { log: () => { throw new Error("No setup secrets may be logged."); } },
  };
  vm.runInNewContext(pageSource, context);
  state.fill = (first = "Mock-only-password-123", second = first) => {
    state.elements.newPassword.value = first;
    state.elements.confirmPassword.value = second;
  };
  state.submit = () => state.elements.setupPasswordForm.listeners.submit({ preventDefault() {} });
  return state;
}

for (const settings of [
  { hash: "" }, { hash: "#token=" }, { hash: "#unrelated=value" },
  { hash: "#token=first&token=second" }, { hash: "", search: "?token=must-never-be-consumed" },
  { replaceFails: true },
]) {
  const p = page(settings);
  assert.equal(p.elements.setupPasswordForm.hidden, true);
  assert.match(p.elements.status.textContent, /invalid or expired/);
  p.fill();
  await p.submit();
  assert.equal(p.calls.length, 0, "Missing or invalid fragment must never make a request.");
}

const success = page({ search: "?tracking=unneeded" });
assert.equal(success.calls.length, 0, "Opening a link must not validate or consume it on GET.");
assert.equal(success.replacements[0][2], "/setup-password");
assert.equal(success.elements.setupPasswordForm.hidden, false);
success.fill("short");
await success.submit();
assert.match(success.elements.status.textContent, /at least 8/);
success.fill("a".repeat(1025));
await success.submit();
assert.match(success.elements.status.textContent, /no more than 1024/);
success.fill("Mock-only-password-123", "different-password");
await success.submit();
assert.match(success.elements.status.textContent, /do not match/);
assert.equal(success.calls.length, 0);
let resolveSetup;
success.fill();
success.fetchHandler = async () => new Promise((resolve) => { resolveSetup = resolve; });
const submitting = success.submit();
await success.submit();
assert.equal(success.calls.length, 1);
assert.equal(success.elements.setupButton.disabled, true);
assert.equal(success.elements.newPassword.disabled, true);
assert.equal(success.calls[0].url, "/api/auth/setup-password");
assert.equal(success.calls[0].options.method, "POST");
assert.equal(success.calls[0].options.credentials, "omit");
assert.equal(success.calls[0].options.referrerPolicy, "no-referrer");
assert.equal(success.calls[0].options.redirect, "error");
assert.deepEqual(JSON.parse(success.calls[0].options.body), {
  token: "mock-token-for-local-tests", new_password: "Mock-only-password-123",
});
resolveSetup(response({ password_set: true }));
await submitting;
assert.equal(success.elements.newPassword.value, "");
assert.equal(success.elements.confirmPassword.value, "");
assert.equal(success.elements.setupPasswordForm.hidden, true);
assert.match(success.elements.status.textContent, /Password set. Sign in/);
assert.equal(success.elements.loginLink.focused, true);
success.fill();
await success.submit();
assert.equal(success.calls.length, 1, "Used token cannot be sent again after success.");
assert.ok(success.calls.every(({ url }) => !url.includes("token") && !url.includes("?")));

for (const label of ["expired", "used", "invalid"]) {
  const p = page({ hash: "#token=" + label + "-mock-token" });
  p.fetchHandler = async () => response({ code: "INVALID_SETUP_LINK", detail: "Untrusted sensitive detail" }, false);
  p.fill();
  await p.submit();
  assert.equal(p.elements.setupPasswordForm.hidden, true);
  assert.equal(p.elements.newPassword.value, "");
  assert.match(p.elements.status.textContent, /invalid or expired/);
  assert.doesNotMatch(p.elements.status.textContent, /Untrusted/);
  p.fill();
  await p.submit();
  assert.equal(p.calls.length, 1, "Invalid token is discarded rather than retried.");
}

for (const failure of ["network", "server", "password", "json", "incomplete"]) {
  const p = page();
  p.fetchHandler = async () => {
    if (failure === "network") throw new Error("Offline");
    if (failure === "incomplete") return response({});
    if (failure === "json") return { ok: true, json: async () => { throw new Error("Interrupted"); } };
    return response({ code: failure === "password" ? "INVALID_PASSWORD" : "TEMPORARY" }, false, failure === "password" ? 422 : 503);
  };
  p.fill();
  await p.submit();
  assert.equal(p.elements.setupButton.disabled, false);
  assert.equal(p.elements.setupPasswordForm.hidden, false);
  assert.equal(p.elements.newPassword.value, "");
  assert.equal(p.elements.confirmPassword.value, "");
  p.fetchHandler = async () => response({ password_set: true });
  p.fill();
  await p.submit();
  assert.equal(p.calls.length, 2);
  assert.match(p.elements.status.textContent, /Password set/);
}

const abandoned = page();
abandoned.fill();
abandoned.events.pagehide();
assert.equal(abandoned.elements.newPassword.value, "");
assert.equal(abandoned.elements.confirmPassword.value, "");
await abandoned.submit();
assert.equal(abandoned.calls.length, 0, "Back/forward restoration must not resurrect abandoned secrets.");

console.log("Setup invitation UI: eligibility, reviewed sends, repeated clicks, provider outcomes, uncertain retries, separate creation, fragment privacy, validation, expiry, success, and navigation checks passed.");
