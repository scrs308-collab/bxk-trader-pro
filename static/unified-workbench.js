(() => {
  "use strict";
  const root = document.getElementById("unifiedWorkbench");
  if (!root) return;
  const runRecovery=document.getElementById("wbRunReconciliation");
  const verifyRecovery=document.getElementById("wbVerifyReconciliation");
  const recoveryStatus=document.getElementById("wbReconciliationStatus");
  const recoveryReceipt=document.getElementById("wbReconciliationRecovery");
  const recoveryKey="bxk-reconciliation-rehearsal-v1";
  let savedRecovery=null;
  try{savedRecovery=JSON.parse(sessionStorage.getItem(recoveryKey));}catch{}
  verifyRecovery.disabled=!savedRecovery;
  runRecovery.addEventListener("click",async()=>{
    runRecovery.disabled=true;
    recoveryStatus.textContent="Running synthetic recovery scenarios...";
    try{
      const response=await fetch("/api/workbench/reconciliation-rehearsal",{method:"POST",credentials:"same-origin"});
      const data=await response.json();
      if(!response.ok||data.synthetic_data!==true||data.submitted!==false||data.all_passed!==true)throw new Error("Rehearsal did not pass.");
      recoveryStatus.textContent="PASS: "+data.checks.map(x=>x.scenario+" → "+x.state+" (retry blocked)").join("; ")+". Synthetic data only; no broker order submitted.";
      savedRecovery=data.restart_receipt;
      try{sessionStorage.setItem(recoveryKey,JSON.stringify(savedRecovery));}catch{}
      verifyRecovery.disabled=false;
      recoveryReceipt.textContent="Restart test prepared: "+savedRecovery.id+". Attempt recorded as SUBMITTING; verify after restarting staging.";
    }catch(error){recoveryStatus.textContent="Verification incomplete: "+error.message;}
    finally{runRecovery.disabled=false;}
  });
  verifyRecovery.addEventListener("click",async()=>{
    if(!savedRecovery)return;
    verifyRecovery.disabled=true;
    try{
      const response=await fetch("/api/workbench/reconciliation-rehearsal/"+encodeURIComponent(savedRecovery.id),{credentials:"same-origin"});
      const data=await response.json();
      const rejected=await fetch("/api/workbench/reconciliation-rehearsal/"+encodeURIComponent(savedRecovery.id)+"/attempt",{method:"POST",credentials:"same-origin"});
      const stable=response.ok&&data.synthetic_data===true&&data.submitted===false&&data.state==="UNKNOWN"
        &&rejected.status===409
        &&data.retry_blocked===true&&data.attempt_count===1
        &&["id","correlation","fingerprint","attempt"].every(k=>data[k]===savedRecovery[k]);
      recoveryReceipt.textContent=stable
        ?"PASS: interrupted attempt recovered as UNKNOWN; original intent and attempt unchanged; one attempt only; duplicate attempt rejected (409). Receipt "+data.id+". No broker order submitted."
        :"Restart recovery not verified. Current state: "+(data.state||"unavailable")+". No broker order submitted.";
    }catch{recoveryReceipt.textContent="Recovery receipt unavailable. Retry remains blocked.";}
    finally{verifyRecovery.disabled=false;}
  });
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
      ? "BXK Auto is unavailable in isolated staging. Use Condor Search for tastytrade market data."
      : mode === "search"
      ? "Condor Search: tastytrade SPXW market data and broker dry-run preview. No live order submission."
      : "Custom Builder: calculate a manually entered iron condor's expiration payoff.";
    if (mode !== "auto") render();
  }
  buttons.forEach(b => b.addEventListener("click", () => setMode(b.dataset.workbenchMode)));
  fields.forEach(k => document.getElementById("wb" + k).addEventListener("input", render));
  const moveSource=document.getElementById("wbExpectedMoveSource");
  moveSource.addEventListener("change",()=>{
    const field=document.getElementById("wbExpectedMove");
    field.readOnly=moveSource.value==="auto";
    field.value="";
    connectionStatus.textContent=moveSource.value==="auto"
      ?"Load SPXW quotes to calculate ATM straddle expected move."
      :"Enter your own 1σ expected move, then load quotes.";
  });
  const reviewPanel=document.getElementById("wbOrderPreview");
  const reviewDetails=document.getElementById("wbPreviewDetails");
  const reviewStatus=document.getElementById("wbPreviewStatus");
  document.getElementById("wbClosePreview").addEventListener("click",()=>{
    reviewPanel.hidden=true;
    reviewDetails.replaceChildren();
    clearConfirmation();
  });
  let selectedReview=null;
  const brokerButton=document.getElementById("wbBrokerPreview");
  const brokerStatus=document.getElementById("wbBrokerPreviewStatus");
  const confirmation=document.getElementById("wbConfirmationRehearsal");
  const confirmCheck=document.getElementById("wbConfirmReview");
  const confirmButton=document.getElementById("wbConfirmSimulation");
  const confirmStatus=document.getElementById("wbConfirmationStatus");
  let validatedReview=null;
  const replayPanel=document.getElementById("wbReplayPanel");
  const replayButton=document.getElementById("wbReplaySimulation");
  const replayStatus=document.getElementById("wbReplayStatus");
  const savedKey="bxk-staging-last-simulation-v1";
  let savedSimulation=null;
  try{savedSimulation=JSON.parse(sessionStorage.getItem(savedKey));}catch{}
  replayPanel.hidden=!savedSimulation;
  document.getElementById("wbForgetSimulation").addEventListener("click",()=>{
    savedSimulation=null;
    try{sessionStorage.removeItem(savedKey);}catch{}
    replayPanel.hidden=true;
  });
  replayButton.addEventListener("click",async()=>{
    if(!savedSimulation)return;
    replayButton.disabled=true;
    replayStatus.textContent="Checking persisted receipt and replay rejection...";
    const post=path=>fetch(path,{method:"POST",credentials:"same-origin",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(savedSimulation.request)});
    try{
      const before=await post("/api/workbench/confirmation-receipt");
      const receipt=await before.json();
      if(!before.ok||receipt.durable_intent_verified!==true)throw new Error("Persisted simulation receipt unavailable.");
      const replay=await post("/api/workbench/confirmation-consume");
      const after=await post("/api/workbench/confirmation-receipt");
      const checked=await after.json();
      const stable=after.ok&&JSON.stringify(receipt)===JSON.stringify(checked)
        &&(!savedSimulation.receipt||JSON.stringify(receipt)===JSON.stringify(savedSimulation.receipt));
      if(replay.status!==409||!stable)throw new Error("Replay or durable receipt verification failed.");
      savedSimulation.receipt=receipt;
      try{sessionStorage.setItem(savedKey,JSON.stringify(savedSimulation));}catch{}
      replayStatus.textContent="PASS: replay rejected (409); durable simulated intent unchanged. Receipt "
        +receipt.receipt_id+"; consumed "+new Date(receipt.consumed_at*1000).toISOString()+". No order submitted.";
    }catch(error){replayStatus.textContent="Verification incomplete: "+error.message;}
    finally{replayButton.disabled=false;}
  });
  const clearConfirmation=()=>{
    validatedReview=null;
    confirmation.hidden=true;
    confirmCheck.checked=false;
    confirmButton.disabled=true;
    confirmStatus.textContent="";
  };
  confirmCheck.addEventListener("change",()=>{
    confirmButton.disabled=!confirmCheck.checked||!validatedReview;
  });
  confirmButton.addEventListener("click",async()=>{
    if(!validatedReview||!confirmCheck.checked)return;
    if(Date.now()-validatedReview.at>30000){
      clearConfirmation();
      confirmStatus.textContent="Server confirmation expired; reload quotes and repeat dry-run.";
      return;
    }
    confirmButton.disabled=true;
    try{
      const response=await fetch("/api/workbench/confirmation-consume",{
        method:"POST",credentials:"same-origin",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({...validatedReview.order,confirmation_token:validatedReview.token})
      });
      const data=await response.json();
      if(response.ok&&data.simulation_only===true&&data.submitted===false&&data.order_intent_status==="SIMULATED_NO_SUBMISSION"){
        savedSimulation={request:{...validatedReview.order,confirmation_token:validatedReview.token}};
        try{sessionStorage.setItem(savedKey,JSON.stringify(savedSimulation));}catch{}
        replayPanel.hidden=false;
        replayStatus.textContent="Simulation saved in this tab. Verify once before and once after the staging restart.";
      }
      confirmStatus.textContent=response.ok&&data.simulation_only===true&&data.order_intent_status==="SIMULATED_NO_SUBMISSION"
        ?"Server durably recorded the simulated order intent and consumed the confirmation. No broker order submitted."
        :"Confirmation rejected: "+(data.detail||response.status);
    }catch{
      confirmStatus.textContent="Confirmation request failed. No order submitted.";
    }finally{
      validatedReview=null;
    }
  });
  const occ=(expiry,type,strike)=>{
    const compact=expiry.slice(2,4)+expiry.slice(5,7)+expiry.slice(8,10);
    return "SPXW  "+compact+type+String(Math.round(strike*1000)).padStart(8,"0");
  };
  brokerButton.addEventListener("click",async()=>{
    if(!selectedReview)return;
    const {c,expiry,selectedAt}=selectedReview;
    const quoteAge=Date.now()-Date.parse(c.oldestQuote||"");
    if(!c.fresh || !Number.isFinite(quoteAge) || quoteAge>120000 || quoteAge< -60000 || Date.now()-selectedAt>30000){
      brokerStatus.textContent="Quote snapshot expired. Reload SPXW quotes before broker dry-run.";
      brokerButton.disabled=true;return;
    }
    brokerButton.disabled=true;
    clearConfirmation();
    brokerStatus.textContent="Requesting tastytrade dry-run (no order submission)...";
    const legs=[
      {symbol:occ(expiry,"P",c.put.short),action:"Sell to Open"},
      {symbol:occ(expiry,"P",c.put.long),action:"Buy to Open"},
      {symbol:occ(expiry,"C",c.call.short),action:"Sell to Open"},
      {symbol:occ(expiry,"C",c.call.long),action:"Buy to Open"}
    ];
    const orderPayload={legs,quantity:1,limit_price:Number(c.premium.toFixed(2))};
    try{
      const response=await fetch("/api/workbench/order-dry-run",{
        method:"POST",credentials:"same-origin",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(orderPayload)
      });
      const data=await response.json();
      if(!response.ok){
        brokerStatus.textContent="Broker dry-run unavailable ("+response.status+"): "+(typeof data.detail==="object" ? ("Broker HTTP "+data.detail.broker_http_status+", code "+data.detail.broker_error_code+". No order submitted.") : (data.detail||"No broker validation returned."));
        return;
      }
      const money=n=>typeof n==="number"&&Number.isFinite(n)?"$"+n.toFixed(2):"Unavailable";
      const lines=[
        "Broker dry-run status: "+(data.broker_status||"Unknown"),
        "Server-verified four-leg quotes: "+(data.server_quote_verified===true?"PASS":"NOT VERIFIED"),
        "Server quote checked: "+(data.server_quote_checked_at||"Unavailable"),
        "Server quote premium: "+(typeof data.server_quote_credit_points==="number"?data.server_quote_credit_points.toFixed(2)+" points":"Unavailable"),
        "BXK defined risk: "+money(data.estimated_defined_risk),
        "Broker buying-power impact: "+money(data.broker_buying_power_change),
        "Broker-reported total fees: "+money(data.broker_total_fees),
        "Difference before fees: "+money(data.difference_from_defined_risk),
        "Unexplained difference after fees: "+money(data.unexplained_difference_after_fees),
        "Buying power remaining: "+money(data.remaining_buying_power),
        "Minimum reserve: "+money(data.minimum_buying_power_reserve),
      ];
      const labels={
        broker_status_received:"Broker status Received",
        order_matches_request:"Four legs, limit price, and order terms match",
        broker_buying_power_internal:"Broker buying-power arithmetic reconciles",
        fees_reported:"Broker returned fee calculation",
        risk_plus_fees_matches_impact:"Defined risk plus fees matches buying-power impact",
        remaining_buying_power_reserve:"Remaining buying power meets reserve",
        broker_warnings_approved:"No unapproved broker warnings",
        broker_errors_absent:"No broker errors"
      };
      for(const [key,label] of Object.entries(labels)){
        lines.push((data.checks?.[key]===true?"PASS: ":"REVIEW: ")+label);
      }
      for(const warning of data.warnings||[]){
        lines.push("Broker warning: "+(warning.message||warning.code||"Unspecified"));
      }
      for(const error of data.errors||[]){
        lines.push("Broker error: "+(error.message||error.code||"Unspecified"));
      }
      lines.push(data.all_checks_pass
        ?"Dry-run checks passed. Staging is review-only; no execution permitted."
        :"Dry-run requires review. Live execution is blocked.");
      brokerStatus.replaceChildren();
      const list=document.createElement("ul");
      for(const line of lines){
        const li=document.createElement("li");li.textContent=line;list.appendChild(li);
      }
      brokerStatus.appendChild(list);
      if(data.all_checks_pass===true && data.server_quote_verified===true && data.execution_authorized===false){
        // Server repeats fresh quote verification and broker dry-run before issuing token.
        const issueResponse=await fetch("/api/workbench/confirmation-issue",{
          method:"POST",credentials:"same-origin",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify(orderPayload)
        });
        const issued=await issueResponse.json();
        if(issueResponse.ok&&issued.simulation_only===true&&issued.confirmation_token){
          validatedReview={at:Date.now(),order:orderPayload,token:issued.confirmation_token};
          confirmation.hidden=false;
          confirmStatus.textContent="Server-issued confirmation valid for 30 seconds. Acknowledge this exact order; simulation only.";
        }else{
          confirmStatus.textContent="Server confirmation not issued: "+(issued.detail||issueResponse.status);
        }
      }
    }catch{
      brokerStatus.textContent="Could not contact broker dry-run endpoint. No order submitted.";
    }finally{
      brokerButton.disabled=false;
    }
  });
  const showReview=(c,widthPut,widthCall,expiry)=>{
    clearConfirmation();
    selectedReview={c,expiry,selectedAt:Date.now()};
    brokerStatus.textContent="Broker buying power not yet checked. Dry-run never places an order.";
    brokerButton.disabled=!c.fresh;
    reviewDetails.replaceChildren();
    const rows=[
      ["Expiration",expiry],
      ["Sell 1 put",c.put.short],["Buy 1 put",c.put.long],
      ["Sell 1 call",c.call.short],["Buy 1 call",c.call.long],
      ["Estimated midpoint premium", "$"+(c.premium*100).toFixed(2)],
      ["Maximum loss (before fees)","$"+c.maxLoss.toFixed(2)],
      ["Estimated breakevens",(c.put.short-c.premium).toFixed(2)+" / "+(c.call.short+c.premium).toFixed(2)],
      ["Modeled POP",c.pop===null?"Unavailable":c.pop.toFixed(2)+"% (approximation)"],
      ["Put / call wing widths",widthPut+" / "+widthCall+" points"],
      ["Oldest quote timestamp",c.oldestQuote||"Unavailable"],
      ["Quote freshness",c.fresh?"Fresh at selection":"Stale or unknown"],
      ["Buying power requirement","Not verified — broker order preview required"],
      ["Trading","Disabled in staging"]
    ];
    const table=document.createElement("table");table.className="bxk-workbench-table";
    const body=document.createElement("tbody");
    rows.forEach(([name,value])=>{
      const tr=document.createElement("tr");
      for(const cellValue of [name,value]){
        const td=document.createElement("td");td.textContent=String(cellValue);tr.appendChild(td);
      }
      body.appendChild(tr);
    });
    table.appendChild(body);reviewDetails.appendChild(table);
    reviewStatus.textContent="Indicative quote snapshot for analysis only. No order has been created or sent to tastytrade.";
    reviewPanel.hidden=false;
    reviewPanel.scrollIntoView({behavior:"smooth",block:"start"});
  };
  const spotInput=document.getElementById("wbLiveSpot");
  const spotSource=document.getElementById("wbSpotSource");
  const spotStatus=document.getElementById("wbSpotStatus");
  async function loadSpot(){
    if(spotSource.value==="manual")return Number(spotInput.value);
    spotInput.value="";
    spotStatus.textContent="Retrieving SPX index quote...";
    try{
      const response=await fetch("/api/workbench/spx-reference",{credentials:"same-origin",cache:"no-store"});
      const data=await response.json();
      if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"SPX index endpoint unavailable");
      if(data.symbol!=="SPX"||!(Number(data.price)>0))throw new Error("Invalid SPX price");
      spotInput.value=Number(data.price).toFixed(2);
      spotStatus.textContent=(data.fresh?"Fresh":"Stale/reference only")+" tastytrade SPX ("+data.price_field+") • "+(data.timestamp||"Timestamp unavailable");
      return Number(data.price);
    }catch(error){
      spotStatus.textContent=(error.message||"SPX quote unavailable")+". Select Manual override.";
      return NaN;
    }
  }
  spotSource.addEventListener("change",()=>{
    spotInput.readOnly=spotSource.value!=="manual";
    spotInput.value="";
    spotStatus.textContent=spotSource.value==="manual"?"Enter SPX price manually (not broker-verified).":"Auto quote will load with SPXW quotes.";
  });
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
      if(data.expirations?.length) await loadSpot();
      connectionStatus.textContent = data.expirations?.length
        ? "SPXW chain connected: " + data.expirations.length + " listed expirations. Load SPXW quotes for current bid/ask prices and modeled POP."
        : "SPXW connected, but no expirations were returned.";
    } catch {
      connectionStatus.textContent = "Could not reach the workbench market-data endpoint.";
    } finally {
      connectButton.disabled = false;
    }
  });
  document.getElementById("wbCondorSort").addEventListener("change",()=>document.getElementById("wbLoadQuotes").click());
  document.getElementById("wbLoadQuotes").addEventListener("click", async () => {
    const spot = spotSource.value==="auto" ? await loadSpot() : Number(spotInput.value);
    const range = Number(document.getElementById("wbLiveRange").value);
    const expiry = document.getElementById("wbLiveExpiry").value;
    const output = document.getElementById("wbQuoteResults");
    output.replaceChildren();
    if (!Number.isFinite(spot) || spot <= 0 || !expiry) {
      output.textContent = "A verified SPX quote is unavailable. Select Manual override or retry, and choose an expiration.";
      return;
    }
    const params = new URLSearchParams({expiration:expiry,
      min_strike:String(spot-range), max_strike:String(spot+range)});
    try {
      const response = await fetch("/api/workbench/quotes?" + params, {credentials:"same-origin",cache:"no-store"});
      if (!response.ok) {output.textContent = "Quotes unavailable ("+response.status+").";return;}
      const data = await response.json();
      if (!data.quotes?.length) {
        const d = data.diagnostics || {};
        output.textContent = `No usable bid/ask quotes. Raw items: ${d.raw_quote_items ?? "?"}; matched symbols: ${d.matched_symbols ?? "?"}; missing bid/ask: ${d.missing_bid_ask ?? "?"}; invalid spreads: ${d.invalid_spreads ?? "?"}.`;
        return;
      }
      const widthPut = Number(document.getElementById("wbPutWing").value);
      const widthCall = Number(document.getElementById("wbCallWing").value);
      const validWidths = [widthPut,widthCall].every(x=>Number.isFinite(x)&&x>0);
      if (!validWidths) {output.textContent="Enter valid put and call wing widths.";return;}
      const quoteMap = new Map(data.quotes.map(q=>[`${q.type}:${Number(q.strike)}`,q]));
      const now = Date.now();
      const fresh = q => {
        const t = Date.parse(q.timestamp || "");
        return Number.isFinite(t) && t <= now + 60000 && now-t <= 120000;
      };
      const makeSpreads = (type,width) => data.quotes
        .filter(q=>q.type===type && (type==="put"?q.strike<spot:q.strike>spot))
        .sort((a,b)=>type==="put"?b.strike-a.strike:a.strike-b.strike)
        .map(short=>{
          const long = quoteMap.get(`${type}:${short.strike+(type==="put"?-width:width)}`);
          if (!long) return null;
          const premium = (Number(short.bid)+Number(short.ask)-Number(long.bid)-Number(long.ask))/2;
          if (!(premium>0 && premium<width)) return null;
          return {type,short:short.strike,long:long.strike,premium,
            fresh:fresh(short)&&fresh(long),timestamp:short.timestamp||"Missing",
          legTimestamps:[short.timestamp,long.timestamp]};
        }).filter(Boolean).slice(0,25);
      const puts=makeSpreads("put",widthPut), calls=makeSpreads("call",widthCall);
      const expectedMoveField=document.getElementById("wbExpectedMove");
      const source=document.getElementById("wbExpectedMoveSource").value;
      let moveExplanation="";
      if(source==="auto"){
        // ATM straddle is approximately sqrt(2/pi) * 1-sigma move
        // under a zero-drift normal terminal-price approximation.
        const strikes=[...new Set(data.quotes.map(q=>Number(q.strike)))].sort((a,b)=>Math.abs(a-spot)-Math.abs(b-spot));
        let chosen=null;
        for(const strike of strikes){
          const put=quoteMap.get("put:"+strike),call=quoteMap.get("call:"+strike);
          if(!put||!call||!fresh(put)||!fresh(call))continue;
          const putMid=(Number(put.bid)+Number(put.ask))/2;
          const callMid=(Number(call.bid)+Number(call.ask))/2;
          if(putMid>0&&callMid>0){chosen={strike,move:(putMid+callMid)*Math.sqrt(Math.PI/2)};break;}
        }
        expectedMoveField.value=chosen?chosen.move.toFixed(2):"";
        moveExplanation=chosen?"ATM "+chosen.strike+" straddle-derived 1σ: "+chosen.move.toFixed(2)+" SPX points.":"Auto expected move unavailable: fresh paired ATM quotes required.";
      }else{
        moveExplanation="Manual expected-move assumption.";
      }
      const expectedMove=Number(expectedMoveField.value);
      const minPop=Number(document.getElementById("wbMinPop").value);
      const popEnabled=expectedMoveField.value.trim()!=="" && Number.isFinite(expectedMove) && expectedMove>0;
      if(expectedMoveField.value.trim()!=="" && !popEnabled){output.textContent="Expected move must be positive.";return;}
      if (!Number.isFinite(minPop)||minPop<1||minPop>99) {
        output.textContent="Minimum modeled POP must be between 1 and 99%.";return;
      }
      const cdf=x=>{
        const z=Math.abs(x),t=1/(1+0.2316419*z);
        const density=Math.exp(-z*z/2)/Math.sqrt(2*Math.PI);
        const tail=density*t*(0.319381530+t*(-0.356563782+t*(1.781477937+t*(-1.821255978+t*1.330274429))));
        return x>=0?1-tail:tail;
      };
      const sortMode=document.getElementById("wbCondorSort").value;
      const combinations=puts.flatMap(p=>calls.map(c=>{
        const premium=p.premium+c.premium;
        const lower=p.short-premium,upper=c.short+premium;
        const pop=popEnabled?100*Math.max(0,Math.min(1,cdf((upper-spot)/expectedMove)-cdf((lower-spot)/expectedMove))):null;
        return {put:p,call:c,premium,
          maxLoss:(Math.max(widthPut,widthCall)-premium)*100,
          fresh:p.fresh&&c.fresh,pop,
          oldestQuote:[...p.legTimestamps,...c.legTimestamps].every(Boolean)
            ? [...p.legTimestamps,...c.legTimestamps].sort()[0] : null};
      })).filter(x=>x.maxLoss>=0 && (!popEnabled || x.pop>=minPop))
        .sort((a,b)=>{
          if(sortMode==="pop" && popEnabled) return b.pop-a.pop || b.premium-a.premium;
          if(sortMode==="riskreward") return (b.maxLoss>0?b.premium*100/b.maxLoss:Infinity)-(a.maxLoss>0?a.premium*100/a.maxLoss:Infinity);
          if(sortMode==="risk") return a.maxLoss-b.maxLoss || b.premium-a.premium;
          return b.premium-a.premium;
        }).slice(0,10);
      const addTable=(heading,columns,rows)=>{
        const title=document.createElement("h3");title.textContent=heading;output.appendChild(title);
        const table=document.createElement("table");table.className="bxk-workbench-table";
        const thead=document.createElement("thead"),tr=document.createElement("tr");
        columns.forEach(c=>{const th=document.createElement("th");th.textContent=c;tr.appendChild(th);});
        thead.appendChild(tr);table.appendChild(thead);
        const tbody=document.createElement("tbody");
        rows.forEach(cells=>{const row=document.createElement("tr");
          cells.forEach(cell=>{const td=document.createElement("td");td.textContent=String(cell);row.appendChild(td);});
          tbody.appendChild(row);});
        table.appendChild(tbody);output.appendChild(table);
      };
      const fmt=n=>Number(n).toFixed(2);
      addTable("Five put spreads",["Sell put","Buy put","Premium (pts)","Max loss ($)","Quote"],
        puts.slice(0,5).map(p=>[p.short,p.long,fmt(p.premium),fmt((widthPut-p.premium)*100),p.fresh?"Fresh":"Stale/unknown"]));
      addTable("Five call spreads",["Sell call","Buy call","Premium (pts)","Max loss ($)","Quote"],
        calls.slice(0,5).map(c=>[c.short,c.long,fmt(c.premium),fmt((widthCall-c.premium)*100),c.fresh?"Fresh":"Stale/unknown"]));
      const comboTitle=document.createElement("h3");
      comboTitle.textContent="Combined iron condors (1 contract)";
      output.appendChild(comboTitle);
      const comboTable=document.createElement("table");
      comboTable.className="bxk-workbench-table";
      const header=document.createElement("thead");
      const headerRow=document.createElement("tr");
      ["Put legs (sell / buy)","Call legs (sell / buy)","Premium ($)","Max loss ($)","Breakevens","Modeled POP","Premium / risk","Quote","Oldest 4-leg timestamp","Analyze"].forEach(label=>{
        const th=document.createElement("th");th.textContent=label;headerRow.appendChild(th);
      });
      header.appendChild(headerRow);comboTable.appendChild(header);
      const comboBody=document.createElement("tbody");
      combinations.forEach(c=>{
        const row=document.createElement("tr");
        const cells=[
          c.put.short+" / "+c.put.long,
          c.call.short+" / "+c.call.long,
          fmt(c.premium*100),
          fmt(c.maxLoss),
          fmt(c.put.short-c.premium)+" / "+fmt(c.call.short+c.premium),
          c.pop===null?"Unavailable":fmt(c.pop)+"%",
          c.maxLoss>0?fmt(c.premium*100/c.maxLoss)+":1":"Undefined",
          c.fresh?"Fresh":"Stale/unknown",
          c.oldestQuote || "Unknown"
        ];
        cells.forEach(value=>{const td=document.createElement("td");td.textContent=value;row.appendChild(td);});
        const actionCell=document.createElement("td");
        const button=document.createElement("button");button.type="button";
        button.className="bxk-mode";button.textContent="Analyze";
        button.disabled=!c.fresh;
        button.title=c.fresh?"Transfer quote snapshot to Custom Builder":"Stale or missing quote timestamps";
        button.addEventListener("click",()=>{
          document.getElementById("wbShortPut").value=c.put.short;
          document.getElementById("wbShortCall").value=c.call.short;
          document.getElementById("wbPutWing").value=widthPut;
          document.getElementById("wbCallWing").value=widthCall;
          document.getElementById("wbCredit").value=fmt(c.premium);
          document.getElementById("wbContracts").value="1";
          showReview(c,widthPut,widthCall,expiry);
        });
        actionCell.appendChild(button);row.appendChild(actionCell);comboBody.appendChild(row);
      });
      comboTable.appendChild(comboBody);output.appendChild(comboTable);
      if(!combinations.length){
        const empty=document.createElement("p");
        empty.textContent="No complete four-leg condors matched the selected wing widths and strike range.";
        output.appendChild(empty);
      }
      const info=document.createElement("p");
      info.textContent="Indicative midpoint premiums from tastytrade, before fees. Quote freshness threshold: 2 minutes. Modeled POP uses the user-entered expected move and a normal-distribution approximation, not broker POP. Analysis only; no order submission.";
      output.appendChild(info);
      connectionStatus.textContent=data.received_quotes+" SPXW quotes received; "+combinations.length+" condors shown. "+(popEnabled?"Modeled POP filter active at "+minPop+"% (approximate, not broker-validated).":"Modeled POP unavailable; filter inactive.")+" Quotes must be refreshed before any future broker order preview.";
    } catch {
      output.textContent = "Could not retrieve SPXW option quotes.";
    }
  });
  setMode("search");
})();
