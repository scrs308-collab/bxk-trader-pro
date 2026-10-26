# Certification owner review

The authenticated recovery panel offers Review for each receipt. It shows the
immutable order, preserved filled quantity, recovery events, registered proof,
broker evidence summaries and owner decisions. Refresh broker evidence uses the
existing read-only certification reader and respects account cooldown and worker
locking. No SQLite transaction is held across broker I/O.

Network timeouts, malformed broker responses and OAuth decoding failures during
owner refreshes use the same durable account backoff as automatic checks. A fresh
worker or repeated owner click cannot bypass the saved delay. Failed reads create
no review evidence and preserve the existing block.

Fresh evidence is stored durably for five minutes, bound to the receipt's scope
and version. The resolution endpoint recalculates allowed decisions inside one
transaction. Stale, expired, consumed, changed-scope or conflicting reviews fail
closed. Each decision requires acknowledgement and a review note; the actor comes
from the authenticated owner configuration, never the request body. POST requests
require the configured same origin. The browser inserts all data as text.

Available decisions:
- KEEP_BLOCKED records the owner's decision while preserving the account block.
- BIND_BROKER_ORDER requires complete fresh broker records and exactly one
  consistent account/correlation/payload match. It binds the broker ID and lifecycle
  without submitting again; partial fills stay recorded and polling resumes.
- CLOSE_WITHOUT_SUBMISSION requires complete fresh records with zero candidates
  AND a separately registered, identity-bound guarded-test proof. The resulting
  RESOLVED_NO_SUBMISSION state releases that receipt's account block, but the
  original intent, attempt, correlation, fingerprint and key remain immutable.

Empty broker history alone cannot authorize closure. For this phase the only
accepted independent proof source is a trusted operator's attestation to the known
guarded certification no-submission test. `register_guarded_test_proof` is an
operator-only Python entry point with no public HTTP counterpart. It binds proof
to the account scope, intent, attempt, correlation and fingerprint, and records
actor, source, evidence reference and time. The operator must verify the harness
and receipt; the function does not magically establish the absence of a prior
submission. Arbitrary user text or a checkbox cannot register this proof.
Genuinely uncertain outcomes without sufficient independent evidence remain blocked.

Evidence, resolution audit, state/version change and transition event use durable
SQLite transactions. The resolution and transition commit together; audit failure
rolls everything back. The review ID is single-use, and concurrent owner decisions
can commit only once. Proof and evidence records are retained, not deleted to clear
a block. A different unresolved receipt in the same scope still blocks the account.

Resolution neither creates a new intent/confirmation token nor changes any broker
order. Original keys and attempts remain non-reusable. A future new order must use
the existing fresh validation and confirmation path; the application still exposes
no broker submission endpoint, and live trading remains disabled.
