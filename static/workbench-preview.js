(() => {
  const button=document.getElementById("checkConnection");
  const status=document.getElementById("connectionStatus");
  const list=document.getElementById("expirationList");
  const expiry=document.getElementById("quoteExpiry");
  const load=document.getElementById("loadQuotes");
  const move=document.getElementById("analysisMove");
  const spotInput=document.getElementById("analysisSpot");
  move.readOnly=true;move.value="";move.placeholder="Auto from ATM quotes";
  const moveStatus=document.createElement("p");moveStatus.setAttribute("role","status");
  move.parentElement.after(moveStatus);
  let latestSnapshot=null;
  spotInput.readOnly=true;spotInput.value="";spotInput.placeholder="Auto: current SPX";
  const spotStatus=document.createElement("p");spotStatus.setAttribute("role","status");
  spotInput.parentElement.after(spotStatus);
  async function refreshReference() {
    spotInput.value="";move.value="";
    spotStatus.textContent="Retrieving current SPX reference...";
    try {
      const response=await fetch("/api/workbench-preview/reference",{credentials:"same-origin",cache:"no-store"});
      if(!response.ok)throw new Error("SPX reference unavailable");
      const data=await response.json();
      const age=Date.now()-Date.parse(data.timestamp);
      if(data.user_scoped!==true || data.order_submission_available!==false || data.symbol!=="SPX" || data.fresh!==true || !Number.isFinite(data.price) || !(data.price>1000 && data.price<100000) || !Number.isFinite(age) || age>120000 || age< -60000)throw new Error("Fresh SPX reference required");
      spotInput.value=data.price.toFixed(2);
      spotStatus.textContent="Auto SPX: tastytrade "+data.price_field+" · "+data.timestamp;
      populateMove();return true;
    } catch {
      spotInput.value="";move.value="";
      spotStatus.textContent="Current SPX unavailable or stale. Retry loading quotes; analysis requires a fresh reference.";
      return false;
    }
  }
  refreshReference();
  function automaticMove(snapshot,spot,expiration,now=Date.now()) {
    if(!snapshot || snapshot.expiration!==expiration || !(spot>0) || !Number.isFinite(spot))return null;
    const quotes=snapshot.quotes||[];
    const strikes=[...new Set(quotes.map(q=>Number(q.strike)).filter(Number.isFinite))];
    strikes.sort((a,b)=>Math.abs(a-spot)-Math.abs(b-spot)||a-b);
    const strike=strikes[0];
    // Never replace an unavailable nearest ATM pair with a farther strike.
    if(strike===undefined || spot<Math.min(...strikes) || spot>Math.max(...strikes))return null;
    const pair=["call","put"].map(type=>quotes.find(q=>q.type===type && Number(q.strike)===strike));
    if(pair.some(q=>!q || !q.fresh || !Number.isFinite(q.bid) || !Number.isFinite(q.ask) || q.bid<0 || q.ask<q.bid || !Number.isFinite(Date.parse(q.timestamp)) || now-Date.parse(q.timestamp)>120000 || now-Date.parse(q.timestamp)<-60000))return null;
    const value=pair.reduce((sum,q)=>sum+(q.bid+q.ask)/2,0)*1.2533;
    return Number.isFinite(value)&&value>0 ? {value,strike} : null;
  }
  function populateMove() {
    const result=automaticMove(latestSnapshot,Number(spotInput.value),expiry.value);
    move.value=result?result.value.toFixed(2):"";
    moveStatus.textContent=result ? "Auto expected move: ATM "+result.strike+" call + put midpoints × 1.2533. Normal-distribution estimate, not broker POP."
      : "Auto expected move unavailable. Enter the SPX reference and load fresh quotes covering its nearest ATM strike.";
    return result;
  }
  spotInput.addEventListener("input",populateMove);
  expiry.addEventListener("change",()=>{latestSnapshot=null;populateMove();document.getElementById("analysisResults").replaceChildren();});
  button.addEventListener("click", async () => {
    latestSnapshot=null;populateMove();
    expiry.replaceChildren(); load.disabled=true;
    button.disabled=true; list.replaceChildren(); status.textContent="Checking your verified broker connection...";
    try {
      const response=await fetch("/api/workbench-preview/expirations", {credentials:"same-origin",cache:"no-store"});
      if(!response.ok) {
        status.textContent=response.status===409 ? "Connect and verify your user-specific tastytrade account in Broker Connect first."
          : response.status===403||response.status===401 ? "An owner session is required."
          : "Expiration data is unavailable. No order was submitted.";
        return;
      }
      const data=await response.json();
      if(data.user_scoped!==true || data.order_submission_available!==false || !Array.isArray(data.expirations)) throw new Error("Unexpected response");
      for(const row of data.expirations) {
        const option=document.createElement("option");option.value=row.date;option.textContent=row.date;expiry.appendChild(option);
        const item=document.createElement("li"); item.textContent=row.date+" ("+row.dte+" DTE)"; list.appendChild(item);
      }
      load.disabled=data.expirations.length===0;
      await refreshReference();
      status.textContent=data.expirations.length+" SPXW expirations received using your broker connection. Order submission is unavailable.";
    } catch { status.textContent="Connection check unavailable. No order was submitted."; }
    finally { button.disabled=false; }
  });
  load.addEventListener("click", async () => {
    const status=document.getElementById("quoteStatus");
    const output=document.getElementById("quoteResults");
    const low=Number(document.getElementById("quoteMin").value);
    const high=Number(document.getElementById("quoteMax").value);
    output.replaceChildren();
    if(!expiry.value || !(low>0 && high>low && high-low<=400)){status.textContent="Select expiration and a positive strike range of at most 400 points.";return;}
    load.disabled=true;status.textContent="Loading bid/ask quotes...";
    try{
      if(!await refreshReference())throw new Error("Fresh SPX reference unavailable. Try again shortly.");
      const params=new URLSearchParams({expiration:expiry.value,min_strike:String(low),max_strike:String(high)});
      const response=await fetch("/api/workbench-preview/quotes?"+params,{credentials:"same-origin",cache:"no-store"});
      if(!response.ok)throw new Error("Quote request rejected ("+response.status+"). Narrow the range or check your connection.");
      const data=await response.json();
      if(data.user_scoped!==true || data.order_submission_available!==false || !Array.isArray(data.quotes))throw new Error("Unexpected quote response");
      latestSnapshot=data;populateMove();
      const table=document.createElement("table");
      for(const cells of [["Type","Strike","Bid","Ask","Quote time","Freshness"],...data.quotes.map(q=>[q.type,q.strike,q.bid,q.ask,q.timestamp||"Unavailable",q.fresh?"Fresh at retrieval":"Stale or unknown"])]){
        const row=document.createElement("tr");for(const value of cells){const cell=document.createElement("td");cell.textContent=String(value);row.appendChild(cell);}table.appendChild(row);
      }
      output.appendChild(table);
      status.textContent=data.received_quotes+" of "+data.requested_contracts+" quotes received. Snapshot only; refresh before review. No order submission.";
    }catch(error){status.textContent=error.message;}
    finally{load.disabled=false;}
  });
  const analyze=document.getElementById("analyzeCondors");
  analyze.addEventListener("click",async()=>{
    const status=document.getElementById("analysisStatus"),output=document.getElementById("analysisResults");
    output.replaceChildren();
    // Refresh the ATM inputs before each analysis; never reuse a stale/manual move.
    move.value="";
    try {
      if(!await refreshReference())throw new Error("Fresh SPX reference unavailable");
      const quoteParams=new URLSearchParams({expiration:expiry.value,min_strike:document.getElementById("quoteMin").value,max_strike:document.getElementById("quoteMax").value});
      const response=await fetch("/api/workbench-preview/quotes?"+quoteParams,{credentials:"same-origin",cache:"no-store"});
      if(!response.ok)throw new Error("Fresh ATM quotes unavailable");
      latestSnapshot=await response.json();
      if(latestSnapshot.user_scoped!==true || latestSnapshot.order_submission_available!==false || !populateMove())throw new Error("Fresh ATM pair unavailable");
    } catch { move.value="";status.textContent="Cannot analyze: auto expected move needs a fresh ATM call and put for the selected expiration.";return; }
    const fields={spot:"analysisSpot",expected_move:"analysisMove",width:"analysisWidth",minimum_pop:"analysisPop",min_strike:"quoteMin",max_strike:"quoteMax"};
    const params=new URLSearchParams({expiration:expiry.value});
    for(const [key,id] of Object.entries(fields)){
      const value=Number(document.getElementById(id).value);
      if(!Number.isFinite(value)||value<=0){status.textContent="Enter valid positive analysis inputs.";return;}
      params.set(key,String(value));
    }
    if(!expiry.value){status.textContent="Check your broker connection and select an expiration first.";return;}
    analyze.disabled=true;status.textContent="Refreshing user quotes and calculating condors...";
    try{
      const response=await fetch("/api/workbench-preview/condors?"+params,{credentials:"same-origin",cache:"no-store"});
      if(!response.ok)throw new Error("Analysis unavailable ("+response.status+"). Check your connection and inputs.");
      const data=await response.json();
      if(data.user_scoped!==true||data.order_submission_available!==false||!Array.isArray(data.condors))throw new Error("Unexpected response");
      const table=document.createElement("table");
      const rows=[["Put sell/buy","Call sell/buy","Credit ($)","Max loss before fees ($)","Breakevens","Modeled POP (%)"]];
      for(const c of data.condors)rows.push([c.put_short+" / "+c.put_long,c.call_short+" / "+c.call_long,c.premium_dollars,c.max_loss_before_fees,c.lower_breakeven+" / "+c.upper_breakeven,c.modeled_pop]);
      for(const cells of rows){const row=document.createElement("tr");for(const value of cells){const cell=document.createElement("td");cell.textContent=String(value);row.appendChild(cell);}table.appendChild(row);}
      output.appendChild(table);
      const reviewOutput=document.createElement("div");output.appendChild(reviewOutput);
      [...table.rows].slice(1).forEach((row,index)=>{
        const cell=document.createElement("td"),button=document.createElement("button");
        button.type="button";button.textContent="Review position";cell.appendChild(button);row.appendChild(cell);
        button.addEventListener("click",async()=>{
          button.disabled=true;reviewOutput.textContent="Refreshing the selected four-leg position...";
          const candidate=data.condors[index],payload=Object.fromEntries(params);
          for(const key of Object.keys(payload))if(key!=="expiration")payload[key]=Number(payload[key]);
          for(const key of ["put_short","put_long","call_short","call_long","credit_points"])payload[key]=candidate[key];
          try{
            const response=await fetch("/api/workbench-preview/position-review",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
            if(!response.ok)throw new Error(response.status===409?"Position or premium changed. Reload condors and select again.":"Position review unavailable ("+response.status+").");
            const reviewed=await response.json();
            if(reviewed.review_lock_issued!==false||reviewed.order_submission_available!==false||reviewed.user_scoped!==true)throw new Error("Unexpected review response");
            const p=reviewed.position;
            reviewOutput.textContent="Verified snapshot: sell put "+p.put_short+", buy put "+p.put_long+", sell call "+p.call_short+", buy call "+p.call_long+
              ". Credit $"+p.premium_dollars+"; maximum loss before fees $"+p.max_loss_before_fees+
              "; breakevens "+p.lower_breakeven+" / "+p.upper_breakeven+". Buying power unverified. No execution lock or order created.";
            const dryButton=document.createElement("button"),dryStatus=document.createElement("div");
            dryButton.type="button";dryButton.textContent="Check broker risk and buying power (dry-run only)";
            reviewOutput.appendChild(document.createElement("br"));reviewOutput.appendChild(dryButton);reviewOutput.appendChild(dryStatus);
            dryButton.addEventListener("click",async()=>{
              dryButton.disabled=true;dryStatus.textContent="Refreshing quotes and checking broker risk...";
              try{
                const response=await fetch("/api/workbench-preview/dry-run",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
                if(!response.ok)throw new Error(response.status===409?"Quotes or position changed. Reload and review again.":"Dry-run unavailable ("+response.status+"). No order submitted.");
                const result=await response.json();
                if(result.order_submission_available!==false||result.review_lock_issued!==false)throw new Error("Unexpected dry-run response");
                dryStatus.replaceChildren();
                const summary=document.createElement("p");
                summary.textContent=result.passed?"Dry-run passed. No order submitted; execution unavailable.":"Dry-run blocked. No order submitted.";
                dryStatus.appendChild(summary);
                const list=document.createElement("ul");
                for(const check of result.checks||[]){const item=document.createElement("li");item.textContent=(check.passed?"PASS: ":"BLOCKED: ")+check.message;list.appendChild(item);}
                dryStatus.appendChild(list);
                if(result.buying_power){
                  const bp=document.createElement("p");
                  bp.textContent="Broker impact $"+result.buying_power.impact+"; fees $"+result.fees+"; remaining $"+result.buying_power.remaining+"; minimum reserve $"+result.minimum_reserve+". Snapshot only.";
                  dryStatus.appendChild(bp);
                }
              }catch(error){dryStatus.textContent=error.message;}
              finally{dryButton.disabled=false;}
            });
          }catch(error){reviewOutput.textContent=error.message;}
          finally{button.disabled=false;}
        });
      });
      status.textContent=data.condors.length+" of "+data.matching_count+" matching condors shown by highest credit. Fresh at calculation only; no broker review or order submission.";
    }catch(error){status.textContent=error.message;}
    finally{analyze.disabled=false;}
  });
})();
