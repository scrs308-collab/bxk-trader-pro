# Certification recovery worker

`staging_certification_worker.py` runs a single read-only recovery check every
five seconds when `BXK_CERT_RECONCILIATION_ENABLED=true`. It selects at most one
due UNKNOWN or ACKNOWLEDGED record per tick in the configured certification
account's `certification-operator` scope. The ledger's durable read backoff,
attempt lease and compare-and-set remain authoritative. Synthetic rehearsal
scopes, READY, SUBMITTING, TERMINAL and MANUAL_REVIEW records are not polled.
Startup still recovers interrupted SUBMITTING records before scheduling reads.

The dedicated `TASTYTRADE_CERT_*` configuration must point to the fixed
`https://api.cert.tastyworks.com` host. Preview must be enabled and live trading
disabled. The only POST this worker performs is a read-scoped OAuth token
exchange. It has no submission, cancellation, replacement or reset operation.
Every fresh token requires account ownership verification. Tokens stay in memory
and are refreshed before expiry; a 401 invalidates the cached token.

Provider errors preserve uncertainty. HTTP 429 and authentication failures pause
the entire account, starting at 30 seconds with exponential backoff capped at
300 seconds. A longer Retry-After is honored. Account cooldown is stored in
SQLite, so a process restart cannot bypass it. Individual intent backoff and
the six-read limit remain durable too. An empty complete collection never
permits resubmission. Exhausted UNKNOWN recovery moves to MANUAL_REVIEW.

Consecutive provider failure counts are also durable and account-scoped. Failures
after a restart retain the 30, 60, 120, 240, 300-second progression; longer broker
Retry-After values still win. A complete successful read resets the count and
cooldown for either automatic checks or owner evidence refreshes. Incomplete
collections do not reset failure history. The added failure-count table preserves
existing cooldown rows without rewriting or deleting them during deployment.

The authenticated `/api/workbench/reconciliation-status` route reads durable
status only. It exposes at most 50 recent certification receipts, filled quantity,
broker lifecycle status, safe reason codes and next check time. It excludes
credentials, account numbers, correlation IDs, canonical orders and raw provider
payloads. The panel refreshes every 15 seconds while its browser tab is visible.
It provides no submission or manual-resolution controls. Recorded fills remain
exposure even after the order becomes terminal.

## Validation boundaries

The sandbox filled-order lost-response/restart case was verified on October 26,
2026 against broker order 2015008. The submission response body was deliberately
discarded; recovery found the exact persisted correlation and payload after an
actual Railway restart. No second order submission occurred.

The sandbox does not model a real order book: under-$3 limit orders fill and
higher-priced limits remain live. Therefore partial fills, conflicting broker
candidates, token expiry and the midnight boundary use explicit injected
responses or clocks in regression tests, rather than being represented as
naturally occurring sandbox executions. They test exposure retention,
monotonic fills, manual-review decisions, token renewal, and UTC history windows.
Actual sandbox no-match and invalid-token reads can additionally exercise the
same deployed reader without placing any order. Do not deliberately flood the
broker to produce a 429.

Sources:
- https://developer.tastytrade.com/docs/sandbox/
- https://developer.tastytrade.com/docs/guides/rate-limits-and-backoff/
- https://developer.tastytrade.com/docs/authentication/oauth2/
