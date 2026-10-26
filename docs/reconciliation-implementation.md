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

## Verified deployment and restart checkpoint

Code commit `8a66f6dee984114daec704893ec0e33fec5e7786` deployed successfully to
the existing isolated staging service as
`d453226f-4cd2-4666-bc77-a656269f057f`. Production was not modified. The source
branch remains `feature/unified-trade-workbench` and live trading stays disabled.

[CI run 40334909076](https://github.com/scrs308-collab/bxk-trader-pro/actions/runs/40334909076)
ran all 49 tests in Linux with no skips and passed JavaScript validation. Its
log reports `Ran 49 tests in 4.301s` and `OK` at 13:55:54 UTC (09:55 EDT).

At 13:59:01 UTC the authenticated Railway rehearsal endpoint returned 200; all
six synthetic scenarios passed, each with retries blocked. The restart receipt
was `ca44c12e-120f-43d7-bce6-7d1a097ccf95`, initially SUBMITTING with one attempt.
Railway confirmed an in-place restart of that deployment. Runtime logs show the
volume remounted at 14:01:26 UTC and application startup completed at 14:01:31.
At 14:02:01 UTC the persisted receipt returned 200 with state UNKNOWN and its
original identity/correlation/fingerprint/attempt intact, and a second attempt
returned 409. Repeating after browser reload at 14:02:07 UTC also passed.

The original confirmation receipt
`50d3cc9852f28d7376c41ccdea5c99a723fc5d8d2cdb6a2c030b1aea065a5c26`
remained unchanged and its replay still returned 409 after this deployment and
restart. No broker orders were submitted. These are deployed synthetic recovery
tests; actual certification-broker validation remains the next integration step.
