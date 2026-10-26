# Reconciliation rehearsal implementation — October 26, 2026

## Delivered scope

`staging_reconciliation.py` implements a durable simulation state machine in
separate SQLite tables on the staging volume. It cannot promote confirmation
receipts into broker orders and has no submission transport. Every attempt is a
synthetic rehearsal; no money-moving integration is implemented or enabled.

- Immutable normalized request with decimal price, sorted legs, order terms and
  quantity; per-scope hashed idempotency keys and globally unique correlation IDs.
- Atomic attempt reservation and append-only transition events. Eight concurrent
  workers can reserve only one attempt. New keys cannot bypass an uncertain
  outcome in the same simulated account.
- Startup recovery changes unfinished SUBMITTING attempts to UNKNOWN, retaining
  the original attempt/correlation/fingerprint. No recovery path resubmits.
- Reconciliation takes a bounded lease, releases the database lock before reads,
  then applies results with a version/lease compare-and-set. A stale worker cannot
  overwrite newer evidence. Result-write failure retains uncertainty.
- Exact broker/account/correlation/order matching, duplicate-page deduplication,
  conflicting-match/manual-review behavior, monotonic filled quantity, and
  terminal-state protection. Partial and cancelled partial fills retain the
  recorded exposure; terminal refers to the order lifecycle, not a closed position.
- Read backoff starts at two seconds, adds zero-to-three-second jitter, and caps
  the base delay at 300 seconds. Six inconclusive UNKNOWN reads require manual
  review. No auto-resolution, reset or automatic retry is exposed.

The simulation namespace must be explicit (`simulation:...`); no real user or
account identifier is needed by the public rehearsal. Account freeze behavior is
intentionally conservative. A future actual execution integration needs a separate
authorized live ledger, renewed confirmation and all original risk gates.

## Certification order reader

`staging_reconciliation_reader.py` provides an injected read-only adapter fixed to
`https://api.cert.tastyworks.com`. Credentials are explicitly supplied by a future
certification operator, never copied from staging's current broker credentials.
It is not exposed through the web app and makes GET requests only.

It reads paginated historical orders over an absolute UTC window overlapping
the attempt by five minutes, includes today's orders regardless of status, and
fetches a known order ID when available. Missing/inconsistent pagination or an
exhausted page cap is incomplete evidence. Per-leg execution records establish
fills, and active-order remaining quantity must reconcile with them. Cancellation
does not turn removed remaining quantity into an execution. Imbalanced fills,
account or request mismatches require review.
Malformed responses, HTTP 401/403/429/5xx and timeouts never authorize a retry.
Conflicting observations of one order are conservatively escalated rather than
guessing which response is newest.

The adapter has offline schema fixtures only. Certification authentication,
identifier echo, actual pagination, fill schemas and broker lifecycle behavior
still require real certification-environment validation. There is no streamer,
cancel/replace operation, submission endpoint, or automatic broker polling worker.

Sources checked October 26:

- [tastytrade retry and correlation semantics](https://developer.tastytrade.com/docs/guides/idempotency-and-retries/)
- [Order search schema and pagination](https://developer.tastytrade.com/reference/orders/getAccountsAccountNumberOrders/)

## Staging controls and persistence test

The owner-authenticated panel runs six synthetic cases: timeout/no match,
accepted order with a lost response, partial fill, fill, rejection, and conflicting
orders. Every case tests that another attempt is rejected. A seventh synthetic
attempt is deliberately left SUBMITTING for the actual restart acceptance test.

The browser retains only the synthetic receipt identifiers in sessionStorage.
After a staging restart, Verify recovery after restart reads the receipt and
attempts the same synthetic reservation, expecting HTTP 409. It requires UNKNOWN,
unchanged identity/correlation/fingerprint/attempt, and one attempt event. The
endpoint has no broker transport even if an assertion fails.

The routes use the existing owner authentication, and construction requires
preview=true and live=false. Unavailable durable storage fails closed. Startup
storage failure leaves the web UI available but does not allow reconciliation.

## Validation

The staging test suite now contains 49 tests. Core tests cover timeout and empty
history, separate-process recovery, concurrent reservation, replacement-key
blocking, payload/account mismatch, incomplete/repeated pages, lost acceptance,
partial/terminal fills, stale workers, read throttling, malformed money, live
flag/storage failure, and transaction rollback. HTTP tests cover owner auth,
startup recovery, duplicate rejection and the unavailable live submission route.

Windows sandbox socket restrictions prevent the two local ASGI TestClient cases
from running here. Only those tests are skipped locally through an explicit
BXK_SKIP_ASGI_SOCKET_TESTS flag; Linux CI runs the full suite without that flag.
The existing staging-only GitHub workflow now runs all staging tests and checks
JavaScript syntax, with read-only repository permissions and no broker secrets.

Actual CI results and Railway restart evidence are recorded in the continuation
report after deployment. Offline fixtures are not claimed as certification proof.
