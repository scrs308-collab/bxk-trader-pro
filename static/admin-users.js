const USERS_URL = "/api/admin/users";
const AUTH_STATUS_URL = "/api/auth/status";

let initialized = false;
let userListRevision = 0;
const usersById = new Map();
const pendingInvitations = new Set();
const uncertainInvitations = new Set();


function byId(id) {
  return document.getElementById(id);
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function setMessage(message, type = "") {
  const element =
    byId("bxkAdminUsersMessage");

  if (!element) {
    return;
  }

  element.className =
    "bxk-admin-users-message" +
    (type ? ` ${type}` : "");

  element.textContent = message || "";
}


function generateTemporaryPassword() {
  const alphabet =
    "ABCDEFGHJKLMNPQRSTUVWXYZ" +
    "abcdefghijkmnopqrstuvwxyz" +
    "23456789" +
    "!@#$%";

  const random =
    new Uint32Array(16);

  crypto.getRandomValues(random);

  return Array.from(
    random,
    (value) =>
      alphabet[
        value % alphabet.length
      ],
  ).join("");
}


function renderShell() {
  const panel =
    byId("adminUsersPanel");

  if (!panel) {
    return false;
  }

  panel.innerHTML = `
    <div class="bxk-admin-users-intro">
      Create and manage BXK application users.
      OWNER accounts are protected and cannot be
      disabled from this panel.
    </div>

    <div class="bxk-admin-users-layout">

      <section class="bxk-admin-users-section">
        <div class="bxk-admin-users-heading">
          Add User
        </div>

        <label class="bxk-admin-users-field">
          <span>Username</span>
          <input
            id="bxkAdminUsername"
            type="text"
            maxlength="100"
            autocomplete="off"
          >
        </label>

        <label class="bxk-admin-users-field">
          <span>Email</span>
          <input
            id="bxkAdminEmail"
            type="email"
            maxlength="320"
            autocomplete="off"
          >
        </label>

        <label class="bxk-admin-users-field">
          <span>Role</span>

          <select id="bxkAdminRole">
            <option value="BETA">
              BETA
            </option>

            <option value="VIEWER">
              VIEWER
            </option>
          </select>
        </label>

        <label class="bxk-admin-users-field">
          <span>Temporary Password</span>

          <div class="bxk-admin-password-row">
            <input
              id="bxkAdminTemporaryPassword"
              type="text"
              minlength="8"
              autocomplete="off"
            >

            <button
              id="bxkGenerateTemporaryPassword"
              class="bxk-admin-users-button secondary"
              type="button"
            >
              GENERATE
            </button>
          </div>
        </label>

        <div class="bxk-admin-users-note">
          The temporary password is not emailed. After creating the account,
          use SEND SETUP LINK below so the user can choose their own password.
          A temporary-password login still requires a password change.
        </div>

        <button
          id="bxkCreateUserButton"
          class="bxk-admin-users-button primary"
          type="button"
        >
          CREATE USER
        </button>
      </section>

      <section class="bxk-admin-users-section">
        <div class="bxk-admin-users-heading">
          Existing Users
        </div>

        <button
          id="bxkRefreshAdminUsers"
          class="bxk-admin-users-button secondary"
          type="button"
        >
          REFRESH USERS
        </button>

        <div
          id="bxkAdminUsersList"
          class="bxk-admin-users-list"
        >
          Loading...
        </div>
      </section>

    </div>

    <div
      id="bxkAdminUsersMessage"
      class="bxk-admin-users-message"
      role="status"
      aria-live="polite"
    ></div>
  `;

  return true;
}


function renderUsers(users) {
  const container =
    byId("bxkAdminUsersList");

  if (!container) {
    return;
  }

  usersById.clear();
  if (Array.isArray(users)) {
    users.forEach((user) => usersById.set(String(user.id), user));
  }

  if (
    !Array.isArray(users) ||
    users.length === 0
  ) {
    container.innerHTML = `
      <div class="bxk-admin-users-empty">
        No BXK users were found.
      </div>
    `;

    return;
  }

  container.innerHTML =
    users.map((user) => {
      const isOwner =
        String(
          user.role || ""
        ).toUpperCase() === "OWNER";

      const isActive =
        user.is_active === true;

      const isBeta =
        String(
          user.role || ""
        ).toUpperCase() === "BETA";

      const broker =
        user.broker || {};

      const brokerConnected =
        broker.connected === true;

      const brokerOAuthEnabled =
        user.broker_oauth_enabled === true;

      const liveTradingEnabled =
        broker.live_trading_enabled === true;

      const subscription =
        user.subscription || {};

      const manualSubscriptionAccess =
        subscription.manual_access_granted === true;

      const subscriptionLabel = isOwner
        ? "OWNER ACCESS"
        : manualSubscriptionAccess
          ? "MANUAL ACCESS"
          : subscription.status ||
            "NO SUBSCRIPTION";

      const action = isOwner
        ? `
          <span class="bxk-admin-owner-protected">
            PROTECTED
          </span>
        `
        : `
          <button
            class="bxk-admin-users-button
              ${isActive ? "danger" : "secondary"}"
            type="button"
            data-user-id="${escapeHtml(user.id)}"
            data-active="${isActive ? "true" : "false"}"
          >
            ${isActive ? "DISABLE" : "ENABLE"}
          </button>
        `;

      const passwordStatus =
        user.must_change_password
          ? "PASSWORD CHANGE REQUIRED"
          : "PASSWORD SET";

      let brokerStatus = "";

      const subscriptionStatus = `
        <span
          class="bxk-admin-live-status
            ${subscription.access_granted ? "active" : "disabled"}"
        >
          SUBSCRIPTION:
          ${escapeHtml(subscriptionLabel)}
        </span>
      `;

      if (isBeta) {
        brokerStatus = `
          <span
            class="bxk-admin-live-status
              ${brokerOAuthEnabled ? "active" : "disabled"}"
          >
            BROKER CONNECT:
            ${brokerOAuthEnabled ? "ON" : "OFF"}
          </span>

          <span class="bxk-admin-broker-status">
            TASTYTRADE:
            ${brokerConnected ? "CONNECTED" : "NOT CONNECTED"}
          </span>

          <span
            class="bxk-admin-live-status
              ${liveTradingEnabled ? "active" : "disabled"}"
          >
            LIVE TRADING:
            ${liveTradingEnabled ? "ON" : "OFF"}
          </span>
        `;
      }

      let liveTradingAction = "";

      let brokerOAuthAction = "";

      const subscriptionAction = isOwner
        ? ""
        : `
          <button
            class="bxk-admin-users-button
              ${manualSubscriptionAccess ? "danger" : "secondary"}"
            type="button"
            data-subscription-user-id="${escapeHtml(user.id)}"
            data-subscription-manual="${manualSubscriptionAccess ? "true" : "false"}"
          >
            ${
              manualSubscriptionAccess
                ? "REMOVE MANUAL ACCESS"
                : "GRANT MANUAL ACCESS"
            }
          </button>
        `;

      if (isBeta) {
        brokerOAuthAction = `
          <button
            class="bxk-admin-users-button
              ${brokerOAuthEnabled ? "danger" : "secondary"}"
            type="button"
            data-oauth-user-id="${escapeHtml(user.id)}"
            data-oauth-enabled="${brokerOAuthEnabled ? "true" : "false"}"
          >
            ${
              brokerOAuthEnabled
                ? "DISABLE BROKER CONNECT"
                : "ENABLE BROKER CONNECT"
            }
          </button>
        `;
      }

      if (isBeta) {
        const canEnable =
          brokerConnected &&
          isActive;

        const disabled =
          !liveTradingEnabled &&
          !canEnable;

        liveTradingAction = `
          <button
            class="bxk-admin-users-button
              ${liveTradingEnabled ? "danger" : "secondary"}"
            type="button"
            data-live-user-id="${escapeHtml(user.id)}"
            data-live-enabled="${liveTradingEnabled ? "true" : "false"}"
            ${disabled ? "disabled" : ""}
          >
            ${
              liveTradingEnabled
                ? "DISABLE LIVE TRADING"
                : brokerConnected
                  ? "ENABLE LIVE TRADING"
                  : "BROKER REQUIRED"
            }
          </button>
        `;
      }

      return `
        <div class="bxk-admin-user-row">

          <div class="bxk-admin-user-identity">
            <strong>
              ${escapeHtml(user.username)}
            </strong>

            <span>
              ${escapeHtml(user.email)}
            </span>
          </div>

          <div class="bxk-admin-user-meta">
            <span class="bxk-admin-role">
              ${escapeHtml(user.role)}
            </span>

            <span
              class="bxk-admin-status
                ${isActive ? "active" : "disabled"}"
            >
              ${isActive ? "ACTIVE" : "DISABLED"}
            </span>

            <span class="bxk-admin-password-status">
              ${passwordStatus}
            </span>

            ${brokerStatus}
            ${subscriptionStatus}
            ${renderInvitationStatus(user.setup_invitation)}
          </div>

          <div class="bxk-admin-user-action">
            ${action}
            ${brokerOAuthAction}
            ${liveTradingAction}
            ${subscriptionAction}
            ${renderInvitationAction(user)}
          </div>

        </div>
      `;
    }).join("");

  container
    .querySelectorAll("button[data-invitation-user-id]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        return sendSetupInvitation(button.dataset.invitationUserId);
      });
    });

  container
    .querySelectorAll(
      "button[data-user-id]"
    )
    .forEach((button) => {
      button.addEventListener(
        "click",
        async () => {
          const userId =
            button.dataset.userId;

          const currentlyActive =
            button.dataset.active === "true";

          await setUserStatus(
            userId,
            !currentlyActive,
          );
        },
      );
    });

  container
    .querySelectorAll(
      "button[data-oauth-user-id]"
    )
    .forEach((button) => {
      button.addEventListener(
        "click",
        async () => {
          const userId =
            button.dataset.oauthUserId;

          const currentlyEnabled =
            button.dataset.oauthEnabled === "true";

          await setBrokerOAuthAccess(
            userId,
            !currentlyEnabled,
          );
        },
      );
    });

  container
    .querySelectorAll(
      "button[data-live-user-id]"
    )
    .forEach((button) => {
      button.addEventListener(
        "click",
        async () => {
          const userId =
            button.dataset.liveUserId;

          const currentlyEnabled =
            button.dataset.liveEnabled === "true";

          await setBrokerLiveTrading(
            userId,
            !currentlyEnabled,
          );
        },
      );
    });

  container
    .querySelectorAll(
      "button[data-subscription-user-id]"
    )
    .forEach((button) => {
      button.addEventListener(
        "click",
        async () => {
          const userId =
            button.dataset.subscriptionUserId;

          const hasManualAccess =
            button.dataset.subscriptionManual === "true";

          await setSubscriptionAccess(
            userId,
            hasManualAccess ? null : true,
          );
        },
      );
    });
}


function isInvitationEligible(user) {
  return user?.setup_invitation_eligible === true &&
    user.is_active === true &&
    user.must_change_password === true &&
    ["BETA", "VIEWER"].includes(String(user.role || "").toUpperCase());
}


function invitationDate(value) {
  if (!value) return "unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "unavailable" : date.toLocaleString();
}


function renderInvitationStatus(invitation) {
  if (!invitation) return "";
  const labels = {
    ACCEPTED: "SETUP EMAIL: ACCEPTED BY PROVIDER (DELIVERY NOT CONFIRMED)",
    FAILED: "SETUP EMAIL: FAILED",
    UNKNOWN: "SETUP EMAIL: SUBMISSION STATUS UNKNOWN",
    USED: "SETUP LINK: USED",
    EXPIRED: "SETUP LINK: EXPIRED",
  };
  const label = labels[invitation.status] || "SETUP EMAIL: STATUS UNAVAILABLE";
  const expiresAt = new Date(invitation.expires_at || "");
  const expired = Number.isFinite(expiresAt.getTime()) && expiresAt.getTime() <= Date.now();
  return `
    <span class="bxk-admin-password-status">
      ${escapeHtml(label)}<br>
      Requested: ${escapeHtml(invitationDate(invitation.created_at))}<br>
      ${expired ? "Link expired" : "Link expires"}: ${escapeHtml(invitationDate(invitation.expires_at))}
    </span>
  `;
}


function renderInvitationAction(user) {
  if (!isInvitationEligible(user)) return "";
  const userId = String(user.id);
  const pending = pendingInvitations.has(userId);
  const uncertain = uncertainInvitations.has(userId);
  return `
    <button
      class="bxk-admin-users-button secondary"
      type="button"
      data-invitation-user-id="${escapeHtml(userId)}"
      ${pending || uncertain ? "disabled" : ""}
    >
      ${pending ? "SENDING SETUP LINK..." : uncertain ? "REFRESH USERS BEFORE RETRY" : "SEND SETUP LINK"}
    </button>
  `;
}


function redrawUsers() {
  renderUsers(Array.from(usersById.values()));
}


async function sendSetupInvitation(userId) {
  userId = String(userId);
  const user = usersById.get(userId);
  if (!isInvitationEligible(user) || pendingInvitations.has(userId) || uncertainInvitations.has(userId)) {
    return;
  }

  const previous = user.setup_invitation
    ? "\nA new link replaces any previous setup link. An unknown submission may already have sent an email."
    : "";
  if (!window.confirm(
    `Send a secure password setup link?\n\nUsername: ${user.username}\nEmail: ${user.email}` +
    "\n\nVerify this account and email address before sending. The user will choose their own password." +
    previous
  )) {
    return;
  }

  pendingInvitations.add(userId);
  userListRevision += 1;
  redrawUsers();
  setMessage(`Submitting setup email for ${user.username}...`);

  try {
    const response = await fetch(
      `${USERS_URL}/${encodeURIComponent(userId)}/setup-invitation`,
      {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_email: user.email,
          expected_username: user.username,
        }),
      },
    );
    const data = await response.json();
    userListRevision += 1;
    if (!response.ok && response.status >= 400 && response.status < 500) {
      const detail = typeof data.detail === "string"
        ? data.detail
        : "Refresh the account and confirm the username and email before trying again.";
      await loadUsers({ reportErrors: false });
      setMessage(`Setup email request was rejected. ${detail}`, "error");
      return;
    }
    const status = data.invitation?.status;
    if (!response.ok || !["ACCEPTED", "FAILED", "UNKNOWN"].includes(status)) {
      throw new Error("Setup email submission could not be confirmed.");
    }
    if (data.user && String(data.user.id) === userId) {
      usersById.set(userId, data.user);
    } else {
      usersById.set(userId, { ...user, setup_invitation: data.invitation });
    }

    if (status === "ACCEPTED") {
      setMessage(
        `Setup email for ${user.username} accepted by the mail provider. Delivery is not confirmed. ` +
        `Link expires: ${invitationDate(data.invitation.expires_at)}.`,
        "success",
      );
    } else if (status === "FAILED") {
      setMessage(
        `Setup email for ${user.username} failed. Review the account and email address before retrying.`,
        "error",
      );
    } else {
      setMessage(
        `Setup email submission for ${user.username} is unknown. It may have been sent. ` +
        "Check with the recipient before sending another link; a new link replaces the previous one.",
        "error",
      );
    }
  } catch (_) {
    // Never automatically repeat an email submission after an uncertain response.
    uncertainInvitations.add(userId);
    const refreshed = await loadUsers({ reportErrors: false });
    setMessage(
      "Setup email submission could not be confirmed and may have been sent. " +
      (refreshed
        ? "The user list has been refreshed. Review the status and check with the recipient before retrying; a new link replaces the previous one."
        : "Use REFRESH USERS to check the status before retrying."),
      "error",
    );
  } finally {
    pendingInvitations.delete(userId);
    redrawUsers();
  }
}


async function setSubscriptionAccess(
  userId,
  granted,
) {
  try {
    const response =
      await fetch(
        `${USERS_URL}/${userId}/subscription-access`,
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            granted,
          }),
        },
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Unable to update subscription access."
      );
    }

    setMessage(
      granted === true
        ? "Manual subscription access granted."
        : "Manual subscription access removed.",
      "success",
    );

    await loadUsers();

  } catch (error) {
    setMessage(
      error.message,
      "error",
    );
  }
}


async function setBrokerOAuthAccess(
  userId,
  enabled,
) {
  const action =
    enabled ? "enable" : "disable";

  try {
    const response =
      await fetch(
        `${USERS_URL}/${userId}/broker-oauth-access`,
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            enabled,
          }),
        },
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        `Unable to ${action} Broker Connect.`
      );
    }

    setMessage(
      enabled
        ? "Broker Connect enabled for BETA user."
        : "Broker Connect disabled for BETA user.",
      "success",
    );

    await loadUsers();

  } catch (error) {
    setMessage(
      error.message,
      "error",
    );
  }
}


async function setBrokerLiveTrading(
  userId,
  enabled,
) {
  const action =
    enabled ? "enable" : "disable";

  if (
    enabled &&
    !window.confirm(
      "Enable LIVE trading for this BETA user? " +
      "This permits real broker order submission " +
      "when the global BXK live-trading switch is also enabled."
    )
  ) {
    return;
  }

  try {
    const response =
      await fetch(
        `${USERS_URL}/${userId}/broker-live-trading`,
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            enabled,
          }),
        },
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        `Unable to ${action} live trading.`
      );
    }

    setMessage(
      enabled
        ? "Live trading enabled for BETA user."
        : "Live trading disabled for BETA user.",
      "success",
    );

    await loadUsers();

  } catch (error) {
    setMessage(
      error.message,
      "error",
    );
  }
}


async function loadUsers({ reportErrors = true } = {}) {
  const revision = ++userListRevision;
  try {
    const response =
      await fetch(
        `${USERS_URL}?_=${Date.now()}`,
        {
          cache: "no-store",
        },
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Unable to load users."
      );
    }

    if (!Array.isArray(data.users)) {
      throw new Error("Unable to verify the current user list.");
    }
    // A stale read must not erase a newer send outcome or unlock uncertain retries.
    if (revision !== userListRevision) return false;
    uncertainInvitations.clear();
    renderUsers(data.users);
    return true;

  } catch (error) {
    if (reportErrors && revision === userListRevision) {
      setMessage(error.message, "error");
    }
    return false;
  }
}


async function createUser() {
  const username =
    byId("bxkAdminUsername")
      ?.value
      .trim();

  const email =
    byId("bxkAdminEmail")
      ?.value
      .trim();

  const role =
    byId("bxkAdminRole")
      ?.value;

  const temporaryPassword =
    byId(
      "bxkAdminTemporaryPassword"
    )?.value;

  const button =
    byId("bxkCreateUserButton");

  if (button?.disabled) return;

  if (
    !username ||
    !email ||
    !temporaryPassword
  ) {
    setMessage(
      "Username, email, and temporary password are required.",
      "error",
    );

    return;
  }

  button.disabled = true;
  button.textContent =
    "CREATING USER...";

  try {
    const response =
      await fetch(
        USERS_URL,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            username,
            email,
            role,
            temporary_password:
              temporaryPassword,
          }),
        },
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Unable to create user."
      );
    }

    byId("bxkAdminUsername").value = "";
    byId("bxkAdminEmail").value = "";

    byId(
      "bxkAdminTemporaryPassword"
    ).value = "";

    setMessage(
      `User ${data.user.username} created successfully. No email has been sent. ` +
      "Review the account below and choose SEND SETUP LINK so the user can set their own password.",
      "success",
    );

    await loadUsers();

  } catch (error) {
    setMessage(
      error.message,
      "error",
    );

  } finally {
    button.disabled = false;
    button.textContent =
      "CREATE USER";
  }
}


async function setUserStatus(
  userId,
  isActive,
) {
  try {
    const response =
      await fetch(
        `${USERS_URL}/${userId}/status`,
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            is_active: isActive,
          }),
        },
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Unable to update user."
      );
    }

    await loadUsers();

  } catch (error) {
    setMessage(
      error.message,
      "error",
    );
  }
}


async function initializeOwnerAccess() {
  try {
    const response =
      await fetch(
        AUTH_STATUS_URL,
        {
          cache: "no-store",
        },
      );

    const data =
      await response.json();

    if (
      !data.authenticated ||
      String(
        data.role || ""
      ).toUpperCase() !== "OWNER"
    ) {
      return;
    }

    const card =
      byId("adminUsersCard");

    if (!card) {
      return;
    }

    card.hidden = false;

    if (!renderShell()) {
      return;
    }

    byId(
      "bxkGenerateTemporaryPassword"
    )?.addEventListener(
      "click",
      () => {
        byId(
          "bxkAdminTemporaryPassword"
        ).value =
          generateTemporaryPassword();
      },
    );

    byId(
      "bxkCreateUserButton"
    )?.addEventListener(
      "click",
      createUser,
    );

    byId("bxkRefreshAdminUsers")?.addEventListener("click", async () => {
      const button = byId("bxkRefreshAdminUsers");
      if (button.disabled) return;
      button.disabled = true;
      try {
        if (await loadUsers()) setMessage("User list and setup email status refreshed.");
      } finally {
        button.disabled = false;
      }
    });

    await loadUsers();

  } catch (error) {
    console.error(
      "Admin user initialization failed:",
      error,
    );
  }
}


export function initializeAdminUsers() {
  if (initialized) {
    return;
  }

  initialized = true;

  initializeOwnerAccess();
}
