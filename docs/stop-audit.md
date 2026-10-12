# Stop Audit (draft implementation)

Stop Audit observes what an explicitly confirmed stopped-out iron condor would
have done after the actual exit. It creates no brokerage position and never
submits, previews, modifies or cancels an order. The actual trade journal and
realized result remain unchanged.

## Current scope

- Tastytrade, original SPXW PM-settled, 1:1 credit iron condors only.
- Authenticated database-backed OWNER/BETA users, exact journal ownership.
  Legacy NULL-owner records are deliberately not adopted.
- The original and closing filled orders are verified in the selected account:
  IDs, symbols, actions, exact quantities, actual prices and execution times.
- Closed condors appear under Performance → Stop Audit awaiting confirmation.
  A generic broker close or a realized loss is never automatically called a stop.
- The user explicitly confirms a stop-out and enters three cost estimates in
  total dollars for the entire position: entry costs, actual exit costs, and
  hypothetical exit costs. Zero must be entered deliberately when appropriate.
- Sampling starts on enrollment, not retrospectively at the close time. The
  pre-enrollment gap is shown. Browser tabs need not remain open.

## Marks, costs and interpretation

Every regular-session minute, the worker retrieves the exact four original
option symbols through that user's Tastytrade connection. It checks every raw
`updated-at` timestamp, symbol, bid/ask, halt state, spread quality and inter-leg
skew. No receipt-time timestamp fallback or stale close-price fallback is used.

- Maximum age: 90 seconds; maximum future tolerance: 5 seconds.
- Maximum inter-leg time skew: 30 seconds.
- Quotes must be at/after tracking start and strictly before expiration cutoff.
- Missing, stale, crossed, non-finite, zero-bid, halted and inconsistent quotes
  are unavailable samples, never zero-value legs or recovery events.
- Midpoint close debit = short-leg mids minus long-leg mids.
- Conservative close estimate = short-leg asks minus long-leg bids.
- Actual estimated net = actual journal gross P/L − entry costs − actual exit costs.
- Hypothetical estimated net = (original entry credit − hypothetical close
  debit) × 100 × contracts − entry costs − hypothetical exit costs.
- The actual stop-close fee is not charged to the hypothetical hold scenario.
  Costs are clearly labeled user estimates, not broker-verified fees.

First breakeven (estimated net ≥ 0), first profit (> 0), and best/worst values
are observed midpoint samples. They are not guaranteed fills or continuous
extrema. Conservative bid/ask estimates are also retained. “Recovery not
observed” does not mean “never recovered.” This self-selected sample alone
cannot establish that changing a stop policy improves trading results.

## Coverage and persistence

Audit records, attempts, quality reasons and quote evidence are database-backed.
A unique (audit, UTC-minute) key makes repeated calls idempotent. The attempt is
committed before network access, so an interrupted request remains an explicit
unavailable observation. Restarts resume outstanding records without inventing
missing samples. Original entry/exit/account identity and cost inputs are frozen.

The screen shows tracking start, pre-enrollment gap, sampled/attempted counts,
last observation, current gap and maximum wall-clock gap. Wall-clock gaps include
closed sessions, holidays, outages and missed intervals; counts are not presented
as a percentage of all possible market observations. The sampler covers regular
sessions only, not SPX global/curb sessions. No old quote path is backfilled.

The selected account fingerprint is checked before each collection. Switching
accounts, losing the connection or losing user eligibility prevents collection
rather than silently falling back to a different account.

## Expiration boundary

Cboe's index-option calendar is conservatively capped by the cash-equity calendar
because the current calendar package omits some Christmas-Eve early closes.
Expiring SPXW's cutoff is 15 minutes before the index-option session close:
16:00 ET normally and 13:00 ET on half days. Missing calendar sessions fail closed.
Regression coverage includes November 27 and December 24, 2026.

No verified automated official-settlement feed exists in this application.
At expiration, the audit transitions to AWAITING_SETTLEMENT with
UNAVAILABLE_VERIFIED_SOURCE_REQUIRED. The expiry hypothetical P/L stays null.
Last observed marks are never presented as final settlement, and missing expired
quotes never imply zero liability. AM-settled SPX is excluded.

A later settlement integration must verify the exact product, date and official
settlement value and use a separate settlement-fee assumption. It must not reuse
hypothetical closing commissions or mutate the original realized result.

## Runtime and API

- GET `/api/stop-audit`: the authenticated user's audits and eligible/ineligible
  closed-trade candidates, limited to the latest 100 of each.
- POST `/api/stop-audit`: explicit enrollment with journal UUID,
  `confirm_stop_out: true`, and all three nonnegative finite cost estimates.
- `BXK_STOP_AUDIT_ENABLED=false` pauses collection and disables new enrollment;
  saved reports remain viewable. The default is enabled, but no collection occurs
  before an audit is explicitly enrolled.
- Preview mode disables the background task along with existing background jobs.
- Worker polls every 60 seconds and bounds each pass to 100 outstanding audits.
  Broker calls are observational. Connection failures create visible gaps.
- Migration `a12b34c56d78` follows `f7c2a91e4d38`, adding `stop_audits` and
  `stop_audit_samples`. No existing trade fields are changed.

## Verification and rollout

This is an unmerged draft for review. No production migration, broker call, deployment,
order operation or historical production backfill is part of preparation.
Before release, run the repository CI including its PostgreSQL migration job;
verify the relevant users have current market-data entitlements and inspect raw
quote timestamps in a controlled read-only account test. No automatic post-stop
history or final-settlement outcome should be promised before those checks.

Historical reconstruction is a separate capability: existing backfill retrieves
orders/transactions, not the missing option quote path. Expired instrument
definitions do not establish historical mark availability. A future importer
must identify its source, granularity, retention, fees and gaps explicitly.
