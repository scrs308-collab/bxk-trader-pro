# Workbench preview readiness — 2026-10-28

## Implemented
- Existing dashboard retained; owner-only dashboard link appears when BXK_WORKBENCH_PREVIEW_ENABLED=true. The flag defaults off.
- /workbench and /api/workbench-preview require owner access and a verified personal tastytrade connection. Workbench data routes do not fall back to installation credentials.
- Bounded SPXW bid/ask snapshots, timestamps, combined-condor analysis, four-leg review and broker dry-run are available. Raw quote and expiration lists are collapsed.
- SPX reference automatically uses a fresh user-scoped SPX last/mark quote, with its timestamp. Closing prices are not substituted for a current reference.
- Expected move automatically uses the nearest ATM call and put midpoints × 1.2533. Missing/stale pairs block analysis. POP remains a normal-distribution approximation, not broker POP.
- Dry-run refreshes legs and premium and applies production validation, exchange-session policy, position/order overlap checks, reserve checks and broker-response reconciliation.
- The preview creates no execution lock, confirmation token or live order. Raw credentials and broker responses are not exposed by its APIs.

## Verification evidence
Before the October 28 UI/data updates, the clean integrated branch passed 1,280 Python tests with 3 skipped, 8 subtests, and 4 JavaScript test files. This is historical evidence, not a full-suite rerun of the latest changes.
October 28 targeted checks verified automatic ATM calculation, missing/stale/foreign-expiration rejection, fresh SPX parsing, rejection of wrong symbols/closing-only/stale data, and disconnected staging-owner setup signaling. JavaScript syntax and HTML control IDs were checked. Browser rendering could not be automated locally because the Playwright browser executable was unavailable; user screenshots confirmed the deployed layout and automatic fields.

The separate bxk-runtime-staging service now runs the full application with a staging PostgreSQL database, database-backed OWNER login and an encrypted personal broker connection. The user confirmed:
- Database authentication succeeds with a populated user UUID.
- Personal tastytrade connection verifies; 39 SPXW expirations load.
- 62/62 quotes received in one selected range; automatic SPX and ATM expected move populate.
- Condor analysis, refreshed position review and real tastytrade dry-run responses work.
- A staging restart preserved the connection: expiration discovery worked without re-entering broker credentials.
- A 10-point-wing preview was blocked at $14,099.20 remaining buying power versus the $15,000 reserve; broker impact $706.88 including $6.88 fees. All other displayed checks passed.
- A 25-point-wing preview was blocked at $12,949.20 remaining versus $15,000; broker impact $1,856.88 including $6.88 fees. All other displayed checks passed.
These screenshots establish broker connectivity and the reserve-blocked path, not a fully passing real-broker dry-run. No broker order was submitted.

Earlier isolated-staging synthetic restart recovery also passed: original identifiers retained, one attempt, duplicate rejected with HTTP 409. Receipt: 8bbe68c5-e6fe-4305-af37-a0b81085b1d4.

## Remaining release checks
- Observe a fully passing real-broker dry-run when the account naturally meets the configured reserve. Do not lower the reserve merely to make this test pass. Mocked success-path coverage already exists in the integration tests.
- Run the full regression suite on the final branch before production promotion; latest incremental changes have targeted checks only.
- Review production integration and approval separately. PR #24 remains the review vehicle; this record does not authorize merging, production deployment or live trading.

Live trading remains disabled in staging. Production promotion and live execution have not been performed by this workflow.
