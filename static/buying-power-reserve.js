const form = document.getElementById("buyingPowerReserveForm");
const input = document.getElementById("myBuyingPowerReserve");
const status = document.getElementById("buyingPowerReserveStatus");

async function loadReserve() {
  const response = await fetch("/api/my-buying-power-reserve", { credentials: "same-origin" });
  if (!response.ok) {
    if (response.status !== 401 && response.status !== 403) status.textContent = "Unable to load reserve.";
    return;
  }
  const data = await response.json();
  input.value = data.min_remaining_buying_power;
  status.textContent = `Current reserve: $${Number(data.min_remaining_buying_power).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const amount = Number(input.value);
  if (!Number.isFinite(amount) || amount < 0) {
    status.textContent = "Enter a valid dollar amount.";
    return;
  }
  status.textContent = "Saving...";
  try {
    const response = await fetch("/api/my-buying-power-reserve", {
      method: "PUT",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ min_remaining_buying_power: amount }),
    });
    if (!response.ok) throw new Error("Save failed");
    const saved = await response.json();
    const verification = await fetch("/api/my-buying-power-reserve", { credentials: "same-origin", cache: "no-store" });
    if (!verification.ok) throw new Error("Verification failed");
    const verified = await verification.json();
    if (Number(verified.min_remaining_buying_power) !== Number(saved.min_remaining_buying_power)) {
      throw new Error("Saved value mismatch");
    }
    input.value = verified.min_remaining_buying_power;
    status.textContent = `Saved $${Number(verified.min_remaining_buying_power).toLocaleString("en-US", { minimumFractionDigits: 2 })} for this account. Build a new trade to use it.`;
  } catch {
    status.textContent = "Reserve could not be saved.";
  }
});

if (form) {
  fetch("/api/auth/status", { credentials: "same-origin" })
    .then((response) => response.json())
    .then((account) => {
      if (String(account.role || "").toUpperCase() === "BETA") return loadReserve();
    })
    .catch(() => { status.textContent = "Unable to load reserve."; });
}
