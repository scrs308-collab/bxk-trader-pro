const SETTINGS_URL = "/api/system-settings";
const BROKER_TEST_URL = "/api/test-new-broker";
const SMS_DIAGNOSTICS_URL = "/api/sms-diagnostics";
const SMS_TEST_URL = "/api/sms-test";

let currentSettings = null;
let initialized = false;


function byId(id) {
  return document.getElementById(id);
}


function setStatus(message, state = "") {
  const element = byId("bxkSettingsStatus");

  if (!element) {
    return;
  }

  element.textContent = message;

  element.className =
    "bxk-settings-message" +
    (state ? ` ${state}` : "");
}


function setConnectionStatus(
  message,
  state = "",
) {
  const element = byId(
    "bxkBrokerConnectionResult"
  );

  if (!element) {
    return;
  }

  element.textContent = message;

  element.className =
    "bxk-settings-connection" +
    (state ? ` ${state}` : "");
}


function configuredLabel(
  configured,
) {
  return configured
    ? "CONFIGURED"
    : "NOT CONFIGURED";
}


function applyConfiguredState(
  id,
  configured,
) {
  const element = byId(id);

  if (!element) {
    return;
  }

  element.textContent =
    configuredLabel(configured);

  element.className =
    configured
      ? "bxk-configured yes"
      : "bxk-configured no";
}


function setSecretPlaceholder(
  id,
  configured,
) {
  const input = byId(id);

  if (!input) {
    return;
  }

  input.value = "";

  input.placeholder = configured
    ? "Configured - leave blank to keep current"
    : "Not configured";
}


function renderSettingsShell() {
  const container = byId(
    "systemSettingsPanel"
  );

  if (!container) {
    return false;
  }

  container.innerHTML = `
    <div class="bxk-settings-intro">
      Credentials are stored locally on this
      BXK installation. Secret values are never
      returned to the browser after they are saved.
    </div>

    <div class="bxk-settings-grid">

      <section class="bxk-settings-section">
        <div class="bxk-settings-heading">
          BXK Application Access
        </div>

        <div class="bxk-settings-note">
          Stores credentials for the future BXK
          login screen. Login enforcement is not
          enabled yet.
        </div>

        <label class="bxk-settings-field">
          <span>Username</span>
          <input
            id="bxkAppUsername"
            type="text"
            autocomplete="username"
          />
        </label>

        <label class="bxk-settings-field">
          <span>
            New Password
            <small
              id="bxkAppPasswordState"
              class="bxk-configured"
            ></small>
          </span>

          <input
            id="bxkAppPassword"
            type="password"
            autocomplete="new-password"
            placeholder="Leave blank to keep current"
          />
        </label>

        <label class="bxk-settings-field">
          <span>Confirm New Password</span>

          <input
            id="bxkAppPasswordConfirm"
            type="password"
            autocomplete="new-password"
            placeholder="Re-enter new password"
          />
        </label>
      </section>


      <section class="bxk-settings-section">
        <div class="bxk-settings-heading">
          Tastytrade OAuth Connection
        </div>

        <div class="bxk-settings-note">
          BXK currently authenticates using the
          OAuth client secret and refresh token.
          Blank secret fields preserve the current
          stored value.
        </div>

        <div class="bxk-settings-static-row">
          <span>Authentication</span>
          <strong id="bxkAuthMode">
            --
          </strong>
        </div>

        <label class="bxk-settings-field">
          <span>
            Client ID
            <small
              id="bxkClientIdState"
              class="bxk-configured"
            ></small>
          </span>

          <input
            id="bxkTastyClientId"
            type="password"
            autocomplete="off"
          />
        </label>

        <label class="bxk-settings-field">
          <span>
            Client Secret
            <small
              id="bxkClientSecretState"
              class="bxk-configured"
            ></small>
          </span>

          <input
            id="bxkTastyClientSecret"
            type="password"
            autocomplete="off"
          />
        </label>

        <label class="bxk-settings-field">
          <span>
            Refresh Token
            <small
              id="bxkRefreshTokenState"
              class="bxk-configured"
            ></small>
          </span>

          <input
            id="bxkTastyRefreshToken"
            type="password"
            autocomplete="off"
          />
        </label>

        <label class="bxk-settings-field">
          <span>
            Account Number
            <small
              id="bxkAccountState"
              class="bxk-configured"
            ></small>
          </span>

          <input
            id="bxkTastyAccount"
            type="password"
            autocomplete="off"
          />
        </label>

        <label class="bxk-settings-field">
          <span>API Base URL</span>

          <input
            id="bxkTastyBaseUrl"
            type="url"
            autocomplete="off"
          />
        </label>
      </section>


      <section class="bxk-settings-section">
        <div class="bxk-settings-heading">
          Legacy Broker Login
        </div>

        <div class="bxk-settings-note">
          Optional. These credentials are not used
          by the current BXK trading engine and are
          retained only for legacy SDK diagnostics.
        </div>

        <label class="bxk-settings-field">
          <span>
            Tastytrade Username
            <small
              id="bxkLegacyUsernameState"
              class="bxk-configured"
            ></small>
          </span>

          <input
            id="bxkTastyUsername"
            type="text"
            autocomplete="off"
          />
        </label>

        <label class="bxk-settings-field">
          <span>
            Tastytrade Password
            <small
              id="bxkLegacyPasswordState"
              class="bxk-configured"
            ></small>
          </span>

          <input
            id="bxkTastyPassword"
            type="password"
            autocomplete="off"
          />
        </label>
      </section>


      <section class="bxk-settings-section">
        <div class="bxk-settings-heading">
          Trading Risk Controls
        </div>

        <div class="bxk-settings-note">
          Changes require a BXK restart before the
          trading engine uses the new limits.
        </div>

        <label class="bxk-settings-field">
          <span>Maximum Order Risk ($)</span>

          <input
            id="bxkMaxOrderRisk"
            type="number"
            min="0.01"
            step="1"
          />
        </label>

        <label class="bxk-settings-field">
          <span>Minimum Order Credit ($)</span>

          <input
            id="bxkMinOrderCredit"
            type="number"
            min="0.01"
            step="0.01"
          />
        </label>

        <label class="bxk-settings-field">
          <span>
            Minimum Remaining Buying Power ($)
          </span>

          <input
            id="bxkMinBuyingPower"
            type="number"
            min="0"
            step="100"
          />
        </label>

        <div class="bxk-settings-static-row">
          <span>Live Trading</span>

          <strong
            id="bxkLiveTradingState"
            class="system-warning"
          >
            --
          </strong>
        </div>

        <div class="bxk-settings-note safety">
          Live trading cannot be enabled or disabled
          from this settings form.
        </div>
      </section>

      <section class="bxk-settings-section">
        <div class="bxk-settings-heading">
          SMS Alert Diagnostics
        </div>

        <div class="bxk-settings-note">
          Verifies the production alert engine,
          consent record, Twilio transport, and both
          risk-monitor background tasks.
        </div>

        <div class="bxk-settings-static-row">
          <span>Alert Engine</span>
          <strong id="bxkSmsEngineState">--</strong>
        </div>

        <div class="bxk-settings-static-row">
          <span>SMS Transport</span>
          <strong id="bxkSmsTransportState">--</strong>
        </div>

        <div class="bxk-settings-static-row">
          <span>Recipient Consent</span>
          <strong id="bxkSmsConsentState">--</strong>
        </div>

        <div class="bxk-settings-static-row">
          <span>Recipient</span>
          <strong id="bxkSmsRecipient">--</strong>
        </div>

        <div class="bxk-settings-static-row">
          <span>Daytime Monitor</span>
          <strong id="bxkDaytimeMonitorState">--</strong>
        </div>

        <div class="bxk-settings-static-row">
          <span>Overnight Monitor</span>
          <strong id="bxkOvernightMonitorState">--</strong>
        </div>

        <div class="bxk-settings-static-row">
          <span>Daytime Risk</span>
          <strong id="bxkDaytimeRiskState">--</strong>
        </div>

        <div class="bxk-settings-static-row">
          <span>Overnight Risk</span>
          <strong id="bxkOvernightRiskState">--</strong>
        </div>

        <div class="bxk-settings-static-row">
          <span>Last Successful Alert</span>
          <strong id="bxkLastSmsAlert">--</strong>
        </div>

        <button
          id="bxkTestSmsButton"
          class="bxk-settings-button secondary"
          type="button"
        >
          SEND TEST SMS
        </button>

        <div
          id="bxkSmsTestResult"
          class="bxk-settings-connection"
        ></div>
      </section>

    </div>


    <div class="bxk-settings-actions">
      <button
        id="bxkTestBrokerButton"
        class="bxk-settings-button secondary"
        type="button"
      >
        TEST CURRENT CONNECTION
      </button>

      <button
        id="bxkSaveSettingsButton"
        class="bxk-settings-button primary"
        type="button"
      >
        SAVE SETTINGS
      </button>
    </div>

    <div
      id="bxkBrokerConnectionResult"
      class="bxk-settings-connection"
    ></div>

    <div
      id="bxkSettingsStatus"
      class="bxk-settings-message"
    ></div>
  `;

  return true;
}


function applySettings(data) {
  currentSettings = data;

  const app = data.app_access || {};
  const tasty = data.tastytrade || {};
  const risk = data.risk || {};

  const username = byId(
    "bxkAppUsername"
  );

  if (username) {
    username.value =
      app.username || "";
  }

  applyConfiguredState(
    "bxkAppPasswordState",
    app.password_configured,
  );

  applyConfiguredState(
    "bxkClientIdState",
    tasty.client_id_configured,
  );

  applyConfiguredState(
    "bxkClientSecretState",
    tasty.client_secret_configured,
  );

  applyConfiguredState(
    "bxkRefreshTokenState",
    tasty.refresh_token_configured,
  );

  applyConfiguredState(
    "bxkAccountState",
    tasty.account_configured,
  );

  applyConfiguredState(
    "bxkLegacyUsernameState",
    tasty.username_configured,
  );

  applyConfiguredState(
    "bxkLegacyPasswordState",
    tasty.password_configured,
  );

  setSecretPlaceholder(
    "bxkTastyClientId",
    tasty.client_id_configured,
  );

  setSecretPlaceholder(
    "bxkTastyClientSecret",
    tasty.client_secret_configured,
  );

  setSecretPlaceholder(
    "bxkTastyRefreshToken",
    tasty.refresh_token_configured,
  );

  setSecretPlaceholder(
    "bxkTastyPassword",
    tasty.password_configured,
  );

  const account = byId(
    "bxkTastyAccount"
  );

  if (account) {
    account.value = "";

    account.placeholder =
      tasty.account_configured
        ? `${tasty.account_number_masked} - leave blank to keep`
        : "Not configured";
  }

  const legacyUsername = byId(
    "bxkTastyUsername"
  );

  if (legacyUsername) {
    legacyUsername.value = "";

    legacyUsername.placeholder =
      tasty.username_configured
        ? "Configured - leave blank to keep current"
        : "Not configured";
  }

  const baseUrl = byId(
    "bxkTastyBaseUrl"
  );

  if (baseUrl) {
    baseUrl.value =
      tasty.base_url || "";
  }

  const authMode = byId(
    "bxkAuthMode"
  );

  if (authMode) {
    authMode.textContent =
      tasty.authentication_mode ||
      "UNKNOWN";
  }

  const maxRisk = byId(
    "bxkMaxOrderRisk"
  );

  if (maxRisk) {
    maxRisk.value =
      risk.max_order_risk ?? "";
  }

  const minCredit = byId(
    "bxkMinOrderCredit"
  );

  if (minCredit) {
    minCredit.value =
      risk.min_order_credit ?? "";
  }

  const minBuyingPower = byId(
    "bxkMinBuyingPower"
  );

  if (minBuyingPower) {
    minBuyingPower.value =
      risk.min_remaining_buying_power ?? "";
  }

  const liveTrading = byId(
    "bxkLiveTradingState"
  );

  if (liveTrading) {
    if (data.live_trading_enabled) {
      liveTrading.textContent = "ENABLED";
      liveTrading.className =
        "system-error";
    } else {
      liveTrading.textContent = "DISABLED";
      liveTrading.className =
        "system-good";
    }
  }
}


function applySmsBoolean(
  id,
  value,
  goodText,
  badText,
) {
  const element = byId(id);

  if (!element) {
    return;
  }

  element.textContent =
    value ? goodText : badText;

  element.className =
    value
      ? "system-good"
      : "system-error";
}


function formatSmsAlertTime(value) {
  if (!value) {
    return "NONE RECORDED";
  }

  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return String(value);
  }

  return date.toLocaleString();
}


function applySmsDiagnostics(data) {
  applySmsBoolean(
    "bxkSmsEngineState",
    data.alerts_enabled === true,
    "ENABLED",
    "DISABLED",
  );

  applySmsBoolean(
    "bxkSmsTransportState",
    data.transport_configured === true,
    "READY",
    "INCOMPLETE",
  );

  applySmsBoolean(
    "bxkSmsConsentState",
    data.consent_active === true,
    "ACTIVE",
    "MISSING",
  );

  applySmsBoolean(
    "bxkDaytimeMonitorState",
    data.daytime_monitor_active === true,
    "ACTIVE",
    "STOPPED",
  );

  applySmsBoolean(
    "bxkOvernightMonitorState",
    data.overnight_monitor_active === true,
    "ACTIVE",
    "STOPPED",
  );

  const recipient =
    byId("bxkSmsRecipient");

  if (recipient) {
    recipient.textContent =
      data.recipient_masked
      || "NOT CONFIGURED";
  }

  const daytimeRisk =
    byId("bxkDaytimeRiskState");

  if (daytimeRisk) {
    daytimeRisk.textContent =
      data.daytime_worst_state
      || "NONE";
  }

  const overnightRisk =
    byId("bxkOvernightRiskState");

  if (overnightRisk) {
    overnightRisk.textContent =
      data.overnight_state
      || "NONE";
  }

  const lastAlert =
    byId("bxkLastSmsAlert");

  if (lastAlert) {
    if (
      data.last_successful_alert_at
    ) {
      const prefix = [
        data.last_successful_alert_scope,
        data.last_successful_alert_state,
      ]
        .filter(Boolean)
        .join(" ");

      lastAlert.textContent =
        `${prefix} ? ${
          formatSmsAlertTime(
            data.last_successful_alert_at
          )
        }`;
    } else {
      lastAlert.textContent =
        "NONE RECORDED";
    }
  }
}


async function loadSmsDiagnostics() {
  try {
    const response = await fetch(
      `${SMS_DIAGNOSTICS_URL}?_=${Date.now()}`,
      {
        cache: "no-store",
      },
    );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail
        || `HTTP ${response.status}`
      );
    }

    applySmsDiagnostics(data);

  } catch (error) {
    console.error(
      "SMS diagnostics load failed:",
      error,
    );

    const result =
      byId("bxkSmsTestResult");

    if (result) {
      result.textContent =
        "Unable to load SMS diagnostics.";

      result.className =
        "bxk-settings-connection error";
    }
  }
}


async function sendSmsTest() {
  const button =
    byId("bxkTestSmsButton");

  const result =
    byId("bxkSmsTestResult");

  if (button) {
    button.disabled = true;
    button.textContent =
      "SENDING...";
  }

  if (result) {
    result.textContent =
      "Sending production-path test SMS...";

    result.className =
      "bxk-settings-connection";
  }

  try {
    const response = await fetch(
      SMS_TEST_URL,
      {
        method: "POST",
      },
    );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail
        || `HTTP ${response.status}`
      );
    }

    if (result) {
      result.textContent =
        `TEST SMS SENT TO ${
          data.recipient_masked
          || "CONFIGURED RECIPIENT"
        }`;

      result.className =
        "bxk-settings-connection success";
    }

    await loadSmsDiagnostics();

  } catch (error) {
    console.error(
      "SMS test failed:",
      error,
    );

    if (result) {
      result.textContent =
        `TEST SMS FAILED: ${
          error.message
          || "Unknown error"
        }`;

      result.className =
        "bxk-settings-connection error";
    }

  } finally {
    if (button) {
      button.disabled = false;
      button.textContent =
        "SEND TEST SMS";
    }
  }
}



async function loadSystemSettings() {
  setStatus(
    "Loading secure configuration...",
  );

  try {
    const response = await fetch(
      SETTINGS_URL,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`
      );
    }

    const data = await response.json();

    applySettings(data);

    setStatus(
      "Configuration loaded.",
      "success",
    );

  } catch (error) {
    console.error(
      "System settings load failed:",
      error,
    );

    setStatus(
      "Unable to load system settings.",
      "error",
    );
  }
}


function numberChanged(
  id,
  currentValue,
) {
  const input = byId(id);

  if (!input) {
    return null;
  }

  const value = Number(input.value);

  if (!Number.isFinite(value)) {
    throw new Error(
      "One or more risk-control values "
      + "are invalid."
    );
  }

  if (value === Number(currentValue)) {
    return null;
  }

  return value;
}


function buildPayload() {
  if (!currentSettings) {
    throw new Error(
      "Settings have not finished loading."
    );
  }

  const payload = {};

  const app = currentSettings.app_access || {};
  const tasty =
    currentSettings.tastytrade || {};
  const risk = currentSettings.risk || {};

  const appUsername =
    byId("bxkAppUsername")?.value.trim()
    || "";

  if (
    appUsername &&
    appUsername !== (app.username || "")
  ) {
    payload.app_username =
      appUsername;
  }

  const appPassword =
    byId("bxkAppPassword")?.value
    || "";

  const appPasswordConfirm =
    byId("bxkAppPasswordConfirm")?.value
    || "";

  if (
    appPassword ||
    appPasswordConfirm
  ) {
    if (
      appPassword !==
      appPasswordConfirm
    ) {
      throw new Error(
        "BXK application passwords "
        + "do not match."
      );
    }

    if (appPassword.length < 8) {
      throw new Error(
        "BXK application password must "
        + "be at least 8 characters."
      );
    }

    payload.app_password =
      appPassword;
  }

  const secretMappings = [
    [
      "bxkTastyClientId",
      "tastytrade_client_id",
    ],
    [
      "bxkTastyClientSecret",
      "tastytrade_client_secret",
    ],
    [
      "bxkTastyRefreshToken",
      "tastytrade_refresh_token",
    ],
    [
      "bxkTastyAccount",
      "tastytrade_account_number",
    ],
    [
      "bxkTastyUsername",
      "tastytrade_username",
    ],
    [
      "bxkTastyPassword",
      "tastytrade_password",
    ],
  ];

  for (
    const [elementId, fieldName]
    of secretMappings
  ) {
    const value =
      byId(elementId)?.value.trim()
      || "";

    if (value) {
      payload[fieldName] = value;
    }
  }

  const baseUrl =
    byId("bxkTastyBaseUrl")?.value.trim()
    || "";

  if (
    baseUrl &&
    baseUrl !== (tasty.base_url || "")
  ) {
    payload.tastytrade_base_url =
      baseUrl;
  }

  const maxRisk = numberChanged(
    "bxkMaxOrderRisk",
    risk.max_order_risk,
  );

  if (maxRisk !== null) {
    payload.max_order_risk =
      maxRisk;
  }

  const minCredit = numberChanged(
    "bxkMinOrderCredit",
    risk.min_order_credit,
  );

  if (minCredit !== null) {
    payload.min_order_credit =
      minCredit;
  }

  const minBuyingPower =
    numberChanged(
      "bxkMinBuyingPower",
      risk.min_remaining_buying_power,
    );

  if (minBuyingPower !== null) {
    payload.min_remaining_buying_power =
      minBuyingPower;
  }

  return payload;
}


async function saveSystemSettings() {
  const button = byId(
    "bxkSaveSettingsButton"
  );

  try {
    const payload = buildPayload();

    if (
      Object.keys(payload).length === 0
    ) {
      setStatus(
        "No settings were changed.",
      );
      return;
    }

    if (button) {
      button.disabled = true;
      button.textContent = "SAVING...";
    }

    setStatus(
      "Saving secure configuration...",
    );

    const response = await fetch(
      SETTINGS_URL,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify(payload),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail
        || `HTTP ${response.status}`
      );
    }

    applySettings(data);

    const appPassword =
      byId("bxkAppPassword");

    const confirm =
      byId("bxkAppPasswordConfirm");

    if (appPassword) {
      appPassword.value = "";
    }

    if (confirm) {
      confirm.value = "";
    }

    setStatus(
      data.restart_required
        ? "Settings saved. Restart BXK Trader Pro to activate the new runtime configuration."
        : "Settings saved.",
      data.restart_required
        ? "warning"
        : "success",
    );

  } catch (error) {
    console.error(
      "System settings save failed:",
      error,
    );

    setStatus(
      error.message
      || "Unable to save settings.",
      "error",
    );

  } finally {
    if (button) {
      button.disabled = false;
      button.textContent =
        "SAVE SETTINGS";
    }
  }
}


async function testBrokerConnection() {
  const button = byId(
    "bxkTestBrokerButton"
  );

  if (button) {
    button.disabled = true;
    button.textContent =
      "TESTING...";
  }

  setConnectionStatus(
    "Testing current runtime connection...",
  );

  try {
    const response = await fetch(
      BROKER_TEST_URL,
      {
        cache: "no-store",
      },
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail
        || `HTTP ${response.status}`
      );
    }

    const statusText = String(
      data.status || ""
    ).toUpperCase();

    const connected =
      data.connected === true
      || data.success === true
      || statusText === "CONNECTED"
      || statusText === "AUTHENTICATED"
      || statusText === "OK";

    if (connected) {
      setConnectionStatus(
        "CURRENT RUNTIME CONNECTION: CONNECTED",
        "success",
      );
    } else {
      setConnectionStatus(
        "Current broker test completed, but BXK did not confirm a connected state.",
        "warning",
      );
    }

  } catch (error) {
    console.error(
      "Broker connection test failed:",
      error,
    );

    setConnectionStatus(
      "CURRENT RUNTIME CONNECTION: FAILED",
      "error",
    );

  } finally {
    if (button) {
      button.disabled = false;
      button.textContent =
        "TEST CURRENT CONNECTION";
    }
  }
}


export function initializeSystemSettings() {
  if (initialized) {
    return;
  }

  if (!renderSettingsShell()) {
    return;
  }

  initialized = true;

  byId(
    "bxkSaveSettingsButton"
  )?.addEventListener(
    "click",
    saveSystemSettings,
  );

  byId(
    "bxkTestBrokerButton"
  )?.addEventListener(
    "click",
    testBrokerConnection,
  );

  byId(
    "bxkTestSmsButton"
  )?.addEventListener(
    "click",
    sendSmsTest,
  );

  loadSystemSettings();
  loadSmsDiagnostics();
}
