const USERS_URL = "/api/admin/users";
const AUTH_STATUS_URL = "/api/auth/status";

let initialized = false;


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
          New users must change this password
          on their first login.
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
          </div>

          <div class="bxk-admin-user-action">
            ${action}
          </div>

        </div>
      `;
    }).join("");

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
}


async function loadUsers() {
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

    renderUsers(data.users || []);

  } catch (error) {
    setMessage(
      error.message,
      "error",
    );
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
      `User ${data.user.username} created successfully.`,
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
