(() => {
  const button=document.getElementById("checkConnection");
  const status=document.getElementById("connectionStatus");
  const list=document.getElementById("expirationList");
  button.addEventListener("click", async () => {
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
        const item=document.createElement("li"); item.textContent=row.date+" ("+row.dte+" DTE)"; list.appendChild(item);
      }
      status.textContent=data.expirations.length+" SPXW expirations received using your broker connection. Order submission is unavailable.";
    } catch { status.textContent="Connection check unavailable. No order was submitted."; }
    finally { button.disabled=false; }
  });
})();