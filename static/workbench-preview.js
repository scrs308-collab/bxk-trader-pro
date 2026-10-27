(() => {
  const button=document.getElementById("checkConnection");
  const status=document.getElementById("connectionStatus");
  const list=document.getElementById("expirationList");
  const expiry=document.getElementById("quoteExpiry");
  const load=document.getElementById("loadQuotes");
  button.addEventListener("click", async () => {
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
      const params=new URLSearchParams({expiration:expiry.value,min_strike:String(low),max_strike:String(high)});
      const response=await fetch("/api/workbench-preview/quotes?"+params,{credentials:"same-origin",cache:"no-store"});
      if(!response.ok)throw new Error("Quote request rejected ("+response.status+"). Narrow the range or check your connection.");
      const data=await response.json();
      if(data.user_scoped!==true || data.order_submission_available!==false || !Array.isArray(data.quotes))throw new Error("Unexpected quote response");
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