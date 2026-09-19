import { initializeAuthUi } from "./auth-ui.js?v=3";


const statusElement = document.getElementById("billingStatus");
const messageElement = document.getElementById("billingMessage");
const monthlyButton = document.getElementById("monthlyCheckout");
const annualButton = document.getElementById("annualCheckout");
const manageButton = document.getElementById("manageBilling");


function showMessage(message, isError = false) {
  messageElement.textContent = message;
  messageElement.classList.toggle("error", isError);
  messageElement.hidden = false;
}


async function responseBody(response) {
  try {
    return await response.json();
  } catch (_error) {
    return {};
  }
}


function requestToken(interval) {
  const key = `bxkCheckoutRequest:${interval}`;
  let token = sessionStorage.getItem(key);

  if (!token) {
    token = crypto.randomUUID();
    sessionStorage.setItem(key, token);
  }

  return token;
}


async function startCheckout(interval, button) {
  button.disabled = true;
  const originalText = button.textContent;
  button.textContent = "Opening Stripe…";

  try {
    const response = await fetch(
      "/api/billing/checkout-session",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interval,
          request_token: requestToken(interval),
        }),
      },
    );
    const body = await responseBody(response);

    if (!response.ok || !body.url) {
      throw new Error(
        body.detail || "Unable to open Stripe Checkout.",
      );
    }

    window.location.assign(body.url);
  } catch (error) {
    showMessage(error.message, true);
    button.disabled = false;
    button.textContent = originalText;
  }
}


async function openPortal() {
  manageButton.disabled = true;
  manageButton.textContent = "Opening Stripe…";

  try {
    const response = await fetch(
      "/api/billing/portal-session",
      { method: "POST" },
    );
    const body = await responseBody(response);

    if (!response.ok || !body.url) {
      throw new Error(
        body.detail || "Unable to open the billing portal.",
      );
    }

    window.location.assign(body.url);
  } catch (error) {
    showMessage(error.message, true);
    manageButton.disabled = false;
    manageButton.textContent = "Manage Billing";
  }
}


function renderStatus(data) {
  const subscription = data.subscription || {};
  const billing = data.billing || {};
  const status = subscription.status || "No paid subscription";
  const plan = subscription.plan || "—";
  const periodEnd = subscription.current_period_end
    ? new Date(subscription.current_period_end).toLocaleDateString()
    : "—";

  statusElement.innerHTML = `
    <strong>Status:</strong> ${status}<br />
    <strong>Plan:</strong> ${plan}<br />
    <strong>Current period ends:</strong> ${periodEnd}
  `;

  const activePaidSubscription =
    subscription.provider === "STRIPE" &&
    ["ACTIVE", "TRIALING", "PAST_DUE"].includes(status);

  monthlyButton.disabled =
    activePaidSubscription ||
    !billing.plans?.MONTHLY?.available;
  annualButton.disabled =
    activePaidSubscription ||
    !billing.plans?.ANNUAL?.available;
  manageButton.disabled = !data.can_manage_billing;

  if (!billing.enabled) {
    showMessage(
      "Self-service billing is not open yet. Existing approved access remains unchanged.",
    );
  }
}


async function loadBilling() {
  await initializeAuthUi();

  const checkout = new URLSearchParams(
    window.location.search,
  ).get("checkout");

  if (checkout === "success") {
    sessionStorage.removeItem("bxkCheckoutRequest:MONTHLY");
    sessionStorage.removeItem("bxkCheckoutRequest:ANNUAL");
    showMessage(
      "Checkout completed. Subscription access will update as soon as Stripe confirms the payment.",
    );
  } else if (checkout === "canceled") {
    showMessage("Checkout was canceled. No subscription change was made.");
  }

  try {
    const response = await fetch(
      "/api/billing/status",
      { cache: "no-store" },
    );
    const body = await responseBody(response);

    if (!response.ok) {
      throw new Error(
        body.detail || "Unable to load billing status.",
      );
    }

    renderStatus(body);
  } catch (error) {
    statusElement.textContent = error.message;
    showMessage(error.message, true);
  }
}


monthlyButton.addEventListener(
  "click",
  () => startCheckout("MONTHLY", monthlyButton),
);
annualButton.addEventListener(
  "click",
  () => startCheckout("ANNUAL", annualButton),
);
manageButton.addEventListener("click", openPortal);

loadBilling();
