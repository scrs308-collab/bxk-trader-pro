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
      results.textContent = "Enter valid strikes, positive wing widths, a credit no greater than the widest wing, and 1–100 contracts.";
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
    <small>Expiration payoff, before commissions and fees. Illustrative credit entered by user; not a live quote. Short put ${p.ShortPut}, long put ${p.ShortPut-p.PutWing}, short call ${p.ShortCall}, long call ${p.ShortCall+p.CallWing}.</small>`;
  }
  function setMode(mode) {
    buttons.forEach(b => {
      const active = b.dataset.workbenchMode === mode;
      b.classList.toggle("active", active);
      b.setAttribute("aria-pressed", String(active));
    });
    manual.hidden = mode === "auto";
    note.hidden = mode !== "search";
    searchPanel.hidden = mode !== "search";
    description.textContent = mode === "auto"
      ? "Existing BXK trading engine and market analysis."
      : mode === "search"
      ? "Condor Search: live chain scanning is pending integration. Hypothetical payoff tools are available below."
      : "Custom Builder: calculate a manually entered iron condor's expiration payoff.";
    if (mode !== "auto") render();
  }
  buttons.forEach(b => b.addEventListener("click", () => setMode(b.dataset.workbenchMode)));
  fields.forEach(k => document.getElementById("wb" + k).addEventListener("input", render));
  const quoteFile = document.getElementById("wbQuoteFile");
  const searchStatus = document.getElementById("wbSearchStatus");
  const searchResults = document.getElementById("wbSearchResults");
  const searchInputs = ["wbSpot", "wbExpiry", "wbMinCredit", "wbMaxCredit", "wbPutWing", "wbCallWing"];
  let quotes = [];
  let page = 0;
  let candidates = [];

  function parseCsv(text) {
    // RFC4180-style quoted cells, including escaped quotes and line breaks.
    const rows = [];
    let row = [], cell = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (ch === '"') {
        if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
        else quoted = !quoted;
      } else if (ch === "," && !quoted) { row.push(cell.trim()); cell = ""; }
      else if ((ch === "\n" || ch === "\r") && !quoted) {
        if (ch === "\r" && text[i + 1] === "\n") i++;
        row.push(cell.trim()); cell = "";
        if (row.some(Boolean)) rows.push(row);
        row = [];
      } else cell += ch;
    }
    if (quoted) throw new Error("Unclosed quote in CSV.");
    row.push(cell.trim());
    if (row.some(Boolean)) rows.push(row);
    if (rows.length < 2) throw new Error("CSV needs a header and at least one quote.");
    const columns = rows.shift().map(v => v.toLowerCase().replace(/^\uFEFF/, ""));
    for (const key of ["expiration", "type", "strike", "bid", "ask"]) {
      if (!columns.includes(key)) throw new Error("Missing CSV column: " + key);
    }
    const result = [];
    for (const cells of rows) {
      const get = key => cells[columns.indexOf(key)] ?? "";
      const type = get("type").trim().toLowerCase();
      const strike = Number(get("strike")), bid = Number(get("bid")), ask = Number(get("ask"));
      const expiry = get("expiration");
      if (!["put", "call", "p", "c"].includes(type) || !/^\d{4}-\d{2}-\d{2}$/.test(expiry) ||
          !Number.isFinite(strike) || strike <= 0 || !Number.isFinite(bid) ||
          !Number.isFinite(ask) || bid < 0 || ask < bid || !get("bid") || !get("ask")) continue;
      result.push({type:type.startsWith("p")?"put":"call",strike,bid,ask,expiry,
        timestamp: columns.includes("timestamp") ? get("timestamp") : ""});
    }
    return result;
  }

  function searchCondors() {
    if (!quotes.length) return;
    const spot = Number(document.getElementById("wbSpot").value);
    const expiry = document.getElementById("wbExpiry").value;
    const minCredit = Number(document.getElementById("wbMinCredit").value);
    const maxCredit = Number(document.getElementById("wbMaxCredit").value);
    const putWidth = Number(document.getElementById("wbPutWing").value);
    const callWidth = Number(document.getElementById("wbCallWing").value);
    if (!Number.isFinite(spot) || spot <= 0 || !expiry || !Number.isFinite(minCredit) ||
      !Number.isFinite(maxCredit) || minCredit < 0 || maxCredit < minCredit ||
      putWidth <= 0 || callWidth <= 0) {
      searchStatus.textContent = "Select an expiration and valid reference price, widths, and credit range.";
      searchResults.replaceChildren();
      return;
    }
    const byKey = new Map(quotes.filter(q=>q.expiry===expiry).map(q=>[`${q.type}:${q.strike}`,q]));
    const puts = quotes.filter(q=>q.expiry===expiry && q.type==="put" && q.strike<spot)
      .sort((a,b)=>b.strike-a.strike).slice(0,5);
    const calls = quotes.filter(q=>q.expiry===expiry && q.type==="call" && q.strike>spot)
      .sort((a,b)=>a.strike-b.strike).slice(0,5);
    candidates = [];
    for (const p of puts) for (const c of calls) {
      const lp = byKey.get(`put:${p.strike-putWidth}`);
      const lc = byKey.get(`call:${c.strike+callWidth}`);
      if (!lp || !lc) continue;
      const credit = (p.bid+p.ask-lp.bid-lp.ask+c.bid+c.ask-lc.bid-lc.ask)/2;
      if (credit <= 0 || credit < minCredit || credit > maxCredit ||
          credit > Math.min(putWidth,callWidth)) continue;
      candidates.push({p:p.strike,c:c.strike,credit,
        loss:(Math.max(putWidth,callWidth)-credit)*100});
    }
    candidates.sort((a,b)=>b.credit-a.credit || a.p-b.p);
    page=0;
    renderSearch();
  }
  function renderSearch() {
    searchStatus.textContent = `${quotes.length} valid imported quotes; ${candidates.length} matching condors. Midpoint estimates, POP unavailable.`;
    searchResults.replaceChildren();
    if (!candidates.length) return;
    const table = document.createElement("table");
    table.className="bxk-workbench-table";
    table.innerHTML="<thead><tr><th>Short put</th><th>Short call</th><th>Est. credit</th><th>Max loss / contract</th><th>POP</th><th>Analysis</th></tr></thead>";
    const body = document.createElement("tbody");
    candidates.slice(page*10,page*10+10).forEach(q=>{
      const tr=document.createElement("tr");
      [q.p,q.c,q.credit.toFixed(2),money(q.loss),"N/A"].forEach(value=>{
        const td=document.createElement("td");td.textContent=String(value);tr.appendChild(td);
      });
      const td=document.createElement("td"), button=document.createElement("button");
      button.type="button";button.textContent="Analyze";button.className="bxk-mode";
      button.addEventListener("click",()=>{
        document.getElementById("wbShortPut").value=q.p;
        document.getElementById("wbShortCall").value=q.c;
        document.getElementById("wbCredit").value=q.credit.toFixed(4);
        setMode("custom");
      });
      td.appendChild(button);tr.appendChild(td);body.appendChild(tr);
    });
    table.appendChild(body);searchResults.appendChild(table);
    const controls=document.createElement("div");
    controls.className="bxk-workbench-modes";
    for (const [label,delta] of [["Previous 10",-1],["Next 10",1]]) {
      const button=document.createElement("button");button.type="button";button.className="bxk-mode";
      button.textContent=label;button.disabled=page+delta<0 || (page+delta)*10>=candidates.length;
      button.addEventListener("click",()=>{page+=delta;renderSearch();});
      controls.appendChild(button);
    }
    searchResults.appendChild(controls);
  }
  quoteFile.addEventListener("change",async()=>{
    quotes=[];candidates=[];searchResults.replaceChildren();
    const file=quoteFile.files?.[0];
    if(!file) return;
    if(file.size>2_000_000) {searchStatus.textContent="CSV must be under 2 MB.";return;}
    try {
      quotes=parseCsv(await file.text());
      const expirations=[...new Set(quotes.map(q=>q.expiry))].sort();
      document.getElementById("wbExpiry").value=expirations[0] || "";
      searchCondors();
    } catch(err) {searchStatus.textContent=err.message;}
  });
  searchInputs.forEach(id=>document.getElementById(id).addEventListener("change",searchCondors));
  setMode("auto");
})();