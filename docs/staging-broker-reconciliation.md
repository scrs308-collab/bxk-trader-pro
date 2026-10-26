# Staging restart verification and future broker reconciliation

## Scope and evidence (2026-10-26)

Live submission remains absent from `staging_preview:app`. Its only broker order
operation is `/orders/dry-run`, gated by explicit preview=true and live=false.
Confirmation consumption and the `SIMULATED_NO_SUBMISSION` record share one SQLite
transaction. A simulated intent must never be promoted into a live submission.

Railway target inspected:

- Project `bxk-unified-workbench-staging` / `dac1ba61-75ef-4892-b748-c1d137dbc0d9`.
- Environment `staging` / `2a6477a2-46b9-48fa-9962-4c0ae60fb52a`.
- Service `bxk-workbench-staging` / `3031cca2-44d6-4608-9f06-1d3998e14dbf`.
- Source `scrs308-collab/bxk-trader-pro`, `feature/unified-trade-workbench`.
- Running commit `b519f23edf28cebfc47bbab3fcc6cc98d9992b6d`, deployment
  `d0f70a25-6dac-4c71-bd85-41628b3b2160` (SUCCESS).
- One replica; `bxk-staging-confirmations` volume mounted at `/data`; no pending changes.

The prior checkpoint reports successful broker dry-run, quote checks, fee
reconciliation and atomic confirmation. Runtime logs independently show HTTP 200
for dry-run, issuance and consumption at 02:33 UTC on October 26 (October 25 EDT).
Those logs do not contain response bodies, so they do not independently prove
every check passed. Railway OAuth exposes variable names only; the presence of
`BXK_LIVE_TRADING_ENABLED` does not prove its value.

Offline verification: 22 staging tests passed, including server quote re-fetch,
stale-quote rejection before broker access, matching broker order and fees,
unexplained fee and unknown warning rejection, explicit live-flag rejection,
eight concurrent consumers with one success, and separate-process persistence.
An injected SQLite constraint failure verifies both token consumption and intent
insertion roll back together. FULL synchronous mode is explicitly required.
Temporary-directory mount shims are test-only; offline results do not establish
Railway host/volume behavior or current broker connectivity.

## Actual Railway restart acceptance procedure — pending authenticated access

Do not call a replay rejection proof of persistence by itself: the 30-second token
may have expired, or the server could have lost the token entirely. Both also
return 409. Establish the durable row before and after restart.

1. Sign in to the isolated staging hostname. Record target IDs, running commit,
   deployment and volume. Verify the isolated app start command and live=false /
   preview=true through trusted runtime evidence. Do not change flags to make a
   test pass.
2. Obtain fresh four-leg quotes and dry-run an exact one-contract order. Retain a
   redacted receipt with server quote timestamp, all check booleans, defined risk,
   buying-power change, fees and unexplained difference. Require all checks true.
3. Issue and consume a token within its TTL. Require `acknowledged=true`,
   `simulation_only=true`, `submitted=false` and
   `order_intent_status=SIMULATED_NO_SUBMISSION`. Keep the token only in private,
   short-lived operator memory, never logs, source or URLs.
4. Replay the exact request immediately and require 409. Verify in the volume's
   ledger that the token hash has a non-null consumed timestamp and exactly one
   matching intent with the expected fingerprint/status. Save counts, hashes and
   timestamps, not credentials or raw tokens.
5. Restart only the identified staging application deployment in place. Record
   shutdown/startup evidence and recovered health. Keep the same mounted volume.
6. Replay the same request after recovery: require 409, no second intent and
   unchanged durable row fingerprint/status/timestamps. If direct volume reads
   are unavailable, first implement a narrowly scoped owner-authenticated receipt
   lookup; it must not disclose raw tokens or enable submission.
7. Independently reserve an intent with a stable test key using an operator
   harness on that same volume, restart, and require the same-key reservation to
   fail 409 while exactly one row remains. A different payload under that key
   must fail too. `reserve_intent` currently has no public HTTP route.
8. Verify every live submission route remains unavailable. Keep the evidence
   marked incomplete if fresh quotes, sign-in or volume inspection is unavailable.

No actual Railway restart/replay or fresh broker result has yet been established
in this continuation. Do not convert this checklist into a passing test report.

## Reconciliation design — proposal only, no live implementation

The broker documents `external-identifier` as a correlation field, not a
deduplication guarantee. Retrying a POST can create another order. The response
field `ext-client-order-id` is system populated and must not be sent as a request
id. The submission reference's introductory wording is inconsistent on this
point; validate the request schema and identifier round-trip in certification
before any future live work.

Sources checked October 26, 2026:

- [Idempotency and retries](https://developer.tastytrade.com/docs/guides/idempotency-and-retries/)
- [Submit Order schema](https://developer.tastytrade.com/reference/orders/postAccountsAccountNumberOrders/)
- [Search Orders](https://developer.tastytrade.com/reference/orders/getAccountsAccountNumberOrders/)
- [Today's Orders](https://developer.tastytrade.com/reference/orders/getAccountsAccountNumberOrdersLive/)
- [Streaming](https://developer.tastytrade.com/docs/concepts/streaming/)

### Durable model

Create a separate future live ledger, never reuse rehearsal rows. Scope uniqueness
by environment, user, broker and account fingerprint plus idempotency key. Store
intent UUID, immutable canonical request and SHA-256 fingerprint, correlation UUID,
quote/dry-run receipt, expiry, state/version, attempt UUID, worker lease, attempt
times, broker order ID/status, reconciliation cursor, and append-only events.
Canonical request includes instrument type, normalized legs with per-leg action
and quantity, limit price/effect, total quantity, order type, TIF and exact account
scope. Use decimal money, not binary floats. Store secrets separately; redact
account identifiers and raw provider responses from logs.

### States and submission boundary

| State | Meaning | Permitted next action |
| --- | --- | --- |
| VALIDATED | Fresh checks passed; no attempt | Explicit user confirmation |
| READY | Confirmation consumed atomically with live intent | One worker may claim |
| SUBMITTING | Durable attempt committed before network call | One POST for that attempt |
| UNKNOWN | Response absent, ambiguous, malformed, or process interrupted | Read-only reconciliation |
| ACKNOWLEDGED | Verified matching broker order ID | Read broker lifecycle |
| REJECTED | Definitive broker rejection verified | New review, no automatic retry |
| MANUAL_REVIEW | Conflicting matches, payload mismatch, exhausted recovery | Owner investigation; submission blocked |
| TERMINAL | Filled, cancelled, expired or rejected broker order | Retain immutable evidence |

Use an atomic compare-and-set on state/version and an account-scoped worker lease.
Commit SUBMITTING before sending; never hold a database transaction across HTTP.
A crash after that commit, even before sending, is UNKNOWN on restart. A lost or
expired lease permits another worker to reconcile; it never authorizes another
POST. Disable automatic transport/proxy retries on order mutations. A local
success-write failure after broker acceptance must also enter recovery, not retry.
Missing or corrupt durable storage blocks all new submission.

### Read-only recovery algorithm

1. On startup recover every unfinished attempt before accepting a new confirmation
   in its account scope. Block equivalent replacement intents as well as exact
   key replays while an outcome is uncertain.
2. If a broker order ID exists, retrieve it in the original account/environment.
   Otherwise page all order history over an overlapping attempt-time window and
   today's orders, including terminal statuses and trading-day rollover. Match
   exact correlation ID and immutable order/account fingerprint. Do not infer
   acceptance from positions, buying power or a similar-looking spread.
3. Exactly one consistent broker order: bind its ID durably, record ACKNOWLEDGED,
   and track fills/remaining quantity/status. Partial fills remain active exposure.
   A broker lifecycle rejection is an acknowledged order outcome, not permission
   to submit again.
4. Zero matches: stay UNKNOWN. A single empty page, exhausted timeout, missing
   stream update or eventually consistent response cannot establish non-submission.
   Retry reads with bounded exponential backoff/jitter, honor rate limits, persist
   progress, then escalate to MANUAL_REVIEW. This design deliberately requires
   stronger evidence than an empty search before any owner-authorized retry.
5. Multiple matches, mismatched account/payload or inconsistent IDs: MANUAL_REVIEW,
   preserve every candidate and block submissions. Never auto-cancel an order.
6. Streaming can wake a reconciliation job, but REST establishes the persisted
   state after reconnects/gaps. Deduplicate events and prevent older events from
   reverting fills or terminal states.

Any future retry needs an explicit operator decision after broker investigation,
a durable resolution event, current quotes/dry-run/risk checks, and renewed user
confirmation. Neither expiry nor deletion of a local key releases an UNKNOWN
intent. Cancel/replace needs its own operation ledger and current broker-state
check; it is outside this change.

### Required certification tests before live consideration

Exercise timeout before/after broker acceptance, accepted response lost before
local commit, process kill at each transition, multiple workers, duplicate user
clicks/new tokens, repeated and mutated keys, empty/late/paginated history, midnight
rollover, missing correlation echo, multiple candidate orders, partial fills,
out-of-order stream events, 429/5xx/auth failures, storage outage and failed
reconciliation writes. Assert no second POST while UNKNOWN and durable recovery
across host restart. Validate identifiers and final broker outcomes in the broker
certification environment. None of these are authorization to enable live trading.
