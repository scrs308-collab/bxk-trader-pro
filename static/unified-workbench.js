(() => {
  "use strict";
  const root = document.getElementById("unifiedWorkbench");
  if (!root) return;
  const buttons = [...root.querySelectorAll("[data-workbench-mode]")];
  const manual = document.getElementById("workbenchManual");
  const description = document.getElementById("workbenchModeDescription");
  const note = document.getElementById("workbenchSearchNote");
  const searchPanel = document.getElementById("workbenchSearch");
  const results = document.getElementById("workbenchResults");
  const fields = ["ShortPut", "ShortCall", "PutWing", "CallWing", "Credit", "Contracts"];
  const values = () => Object.fromEntries(fields.map(k => [k, Number(document.getElementById("wb" + k).value)]));
  const money = n => Number.isFinite(n) ? n.toLocaleString("en-US", {style:"currency", currency:"USD", maximumFractionDigits:2}) : "—";
  const payoff = (spot, p) => {
    const put = Math.max(p.ShortPut - spot, 0) - Math.max(p.ShortPut - p.PutWing - spot, 0);
    const call = Math.max(spot - p.ShortCall, 0) - Math.max(spot - (p.ShortCall + p.CallWing), 0);
    return (p.Credit - put - call) * 100 * p.Contracts;
  };
  function render() {
    const p = values();
    const valid = fields.every(k => Number.isFinite(p[k])) &&
      p.ShortPut > 0 && p.ShortCall > p.ShortPut &&
      p.PutWing > 0 && p.CallWing > 0 && p.Credit >= 0 &&
      Number.isInteger(p.Contracts) && p.Contracts >= 1 && p.Contracts <= 100 &&
      p.Credit <= Math.max(p.PutWing, p.CallWing);
    if (!valid) {
      results.textContent = "Enter valid strikes, positive wing widths, a premium no greater than the widest wing, and 1–100 contracts.";
      return;
    }
    const maxProfit = p.Credit * 100 * p.Contracts;
    const maxLoss = (Math.max(p.PutWing, p.CallWing) - p.Credit) * 100 * p.Contracts;
    const min = p.ShortPut - p.PutWing - 20, max = p.ShortCall + p.CallWing + 20;
    const points = Array.from({length:81}, (_, i) => {
      const x = min + (max - min) * i / 80;
      return [x, payoff(x,p)];
    });
    const floor = -Math.max(maxLoss, 1), ceil = Math.max(maxProfit, 1);
    const scaleY = y => 125 - (y - floor) / (ceil - floor) * 110;
    const polyline = points.map(([x,y],i) => `${(i/80*600).toFixed(2)},${scaleY(y).toFixed(2)}`).join(" ");
    results.innerHTML = `<div class="bxk-workbench-metrics">
      <span>Max profit <strong>${money(maxProfit)}</strong></span>
      <span>Max loss <strong>${money(maxLoss)}</strong></span>
      <span>Lower breakeven <strong>${(p.ShortPut-p.Credit).toFixed(2)}</strong></span>
      <span>Upper breakeven <strong>${(p.ShortCall+p.Credit).toFixed(2)}</strong></span>
      <span>Estimated POP <strong>Unavailable</strong></span>
    </div>
    <svg viewBox="0 0 600 145" role="img" aria-label="Hypothetical iron condor expiration profit and loss diagram" style="width:100%;max-height:240px">
      <line x1="0" x2="600" y1="${scaleY(0)}" y2="${scaleY(0)}" stroke="currentColor" opacity=".45" />
      <polyline points="${polyline}" fill="none" stroke="#22c55e" stroke-width="3" />
    </svg>
    <small>Expiration payoff, before commissions and fees. Illustrative premium entered by user; not a live quote. Short put ${p.ShortPut}, long put ${p.ShortPut-p.PutWing}, short call ${p.ShortCall}, long call ${p.ShortCall+p.CallWing}.</small>`;
  }
  function setMode(mode) {
    buttons.forEach(b => {
      const active = b.dataset.workbenchMode === mode;
      b.classList.toggle("active", active);
      b.setAttribute("aria-pressed", String(active));
    });
    document.getElementById("tradeSetup").classList.toggle("bxk-manual-mode", mode !== "auto");
    manual.hidden = mode === "auto";
    note.hidden = mode !== "search";
    searchPanel.hidden = mode !== "search";
    description.textContent = mode === "auto"
      ? "Existing BXK trading engine and market analysis."
      : mode === "search"
      ? "Condor Search: tastytrade market-data connection pending. No quotes or search results are available yet."
      : "Custom Builder: calculate a manually entered iron condor's expiration payoff.";
    if (mode !== "auto") render();
  }
  buttons.forEach(b => b.addEventListener("click", () => setMode(b.dataset.workbenchMode)));
  fields.forEach(k => document.getElementById("wb" + k).addEventListener("input", render));
  const connectButton = document.getElementById("wbConnectMarket");
  const connectionStatus = document.getElementById("wbSearchStatus");
  connectButton.addEventListener("click", async () => {
    connectButton.disabled = true;
    connectionStatus.textContent = "Checking authenticated tastytrade SPXW chain access...";
    try {
      const response = await fetch("/api/workbench/expirations", {credentials:"same-origin",cache:"no-store"});
      if (!response.ok) {
        connectionStatus.textContent = response.status === 403 || response.status === 401
          ? "Sign in as the BXK owner to access tastytrade market data."
          : "Tastytrade data unavailable in staging (" + response.status + ").";
        return;
      }
      const data = await response.json();
      const expirySelect = document.getElementById("wbLiveExpiry");
      expirySelect.replaceChildren();
      for (const expiry of data.expirations || []) {
        const opt = document.createElement("option");
        opt.value = expiry.date;
        opt.textContent = expiry.date + " (" + expiry.dte + " DTE)";
        expirySelect.appendChild(opt);
      }
      document.getElementById("wbLoadQuotes").disabled = !data.expirations?.length;
      connectionStatus.textContent = data.expirations?.length
        ? "SPXW chain connected: " + data.expirations.length + " listed expirations. Live option quotes and POP not yet connected."
        : "SPXW connected, but no expirations were returned.";
    } catch {
      connectionStatus.textContent = "Could not reach the workbench market-data endpoint.";
    } finally {
      connectButton.disabled = false;
    }
  });
  document.getElementById("wbLoadQuotes").addEventListener("click", async () => {
    const spot = Number(document.getElementById("wbLiveSpot").value);
    const range = Number(document.getElementById("wbLiveRange").value);
    const expiry = document.getElementById("wbLiveExpiry").value;
    const output = document.getElementById("wbQuoteResults");
    output.replaceChildren();
    if (!Number.isFinite(spot) || spot <= 0 || !expiry) {
      output.textContent = "Enter a current SPX reference price and select an expiration.";
      return;
    }
    const params = new URLSearchParams({expiration:expiry,
      min_strike:String(spot-range), max_strike:String(spot+range)});
    try {
      const response = await fetch("/api/workbench/quotes?" + params, {credentials:"same-origin",cache:"no-store"});
      if (!response.ok) {output.textContent = "Quotes unavailable ("+response.status+").";return;}
      const data = await response.json();
      if (!data.quotes?.length) {
        output.textContent = "No usable bid/ask quotes returned. Verify SPXW quote permissions and market session.";
        return;
      }
      const table = document.createElement("table");
      table.className = "bxk-workbench-table";
      table.innerHTML = "<thead><tr><th>Type</th><th>Strike</th><th>Bid</th><th>Ask</th><th>Quote timestamp</th></tr></thead>";
      const tbody = document.createElement("tbody");
      for (const quote of data.quotes.slice(0,160)) {
        const row = document.createElement("tr");
        for (const value of [quote.type, quote.strike, quote.bid, quote.ask, quote.timestamp || "Not provided"]) {
          const cell = document.createElement("td");
          cell.textContent = String(value);
          row.appendChild(cell);
        }
        tbody.appendChild(row);
      }
      table.appendChild(tbody);
      output.appendChild(table);
      connectionStatus.textContent = data.received_quotes + " SPXW quotes from tastytrade. Check timestamps before use. Order placement remains disabled.";
    } catch {
      output.textContent = "Could not retrieve SPXW option quotes.";
    }
  });
  setMode("auto");
})();