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
    input.value = saved.min_remaining_buying_power;
    status.textContent = "Saved. New trade checks use this reserve.";
  } catch {
    status.textContent = "Reserve could not be saved.";
  }
});

if (form) loadReserve().catch(() => { status.textContent = "Unable to load reserve."; });
