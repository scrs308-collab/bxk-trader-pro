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
})();