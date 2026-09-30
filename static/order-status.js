// Only an explicit broker fill status completes the lifecycle.
export function brokerOrderLifecycle(value) {
  const status = String(value || "").toLowerCase().replace(/[^a-z]/g, "");
  if (status === "filled") return { state: "filled", title: "ORDER FILLED", terminal: true };
  if (["cancelled", "canceled", "rejected", "expired", "removed"].includes(status)) {
    return { state: "failed", title: `ORDER ${status.toUpperCase()}`, terminal: true };
  }
  if (status === "partiallyfilled" || status === "partialfill") {
    return { state: "pending", title: "ORDER PARTIALLY FILLED", terminal: false };
  }
  if (["received", "accepted", "pending", "working", "live", "queued", "routed", "inflight", "contingent", "cancelrequested", "replacepending"].includes(status)) {
    return { state: "pending", title: "ORDER PENDING", terminal: false };
  }
  return { state: "submitted", title: "ORDER SUBMITTED — VERIFYING", terminal: false };
}
