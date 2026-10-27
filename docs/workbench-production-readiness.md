# Workbench preview readiness — 2026-10-27

## Implementation complete on feature/unified-trade-workbench
- Production root preserves the existing dashboard in static/production-dashboard.html.
- Separate /workbench page and /api/workbench-preview endpoints are owner-only and gated by BXK_WORKBENCH_PREVIEW_ENABLED (default off).
- Verified user-specific tastytrade connection required. No fallback to global owner credentials.
- Expiration discovery, bounded bid/ask snapshots, timestamps, combined-condor analysis and fresh position review implemented.
- SPX reference and expected-move assumptions are explicitly manual in the integrated preview; POP is a normal approximation, not broker POP.
- Dry-run refreshes selected legs and premium, uses existing production validation, session policy, held-position and pending-order overlap checks, per-user buying-power reserve, and broker preflight evaluation.
- Dry-run never creates an execution review lock, confirmation token or live order. Broker errors block success. API responses exclude raw account identifiers and raw broker responses.
- Exchange expiration validation uses Eastern time.
- Staging test controls are collapsed outside the normal results flow.

## Validation
202 targeted tests plus 8 subtests passed locally, covering order safety, owner authorization, per-user broker resolution, pending orders, isolated staging and the new HTTP analysis → review → dry-run flow.
New integration tests use simulated broker responses with real production validation helpers. They do not establish live connectivity for the new production-runtime route.
JavaScript syntax checks passed.

The earlier isolated staging workflow was exercised with real quotes and broker dry-runs. Railway restart rehearsal passed with receipt 8bbe68c5-e6fe-4305-af37-a0b81085b1d4: UNKNOWN recovery, original identifiers retained, one attempt, duplicate rejected with 409.

## Remaining release gate
The current Railway staging service runs staging_preview:app, not server:app. It therefore does not expose the newly integrated production-runtime /workbench route.
Before production promotion, run server:app in a separate staging runtime with a staging user database and that user's verified broker connection, enable the preview flag there only, and verify the new page with real quote and dry-run responses.
Do not point isolated staging at production databases or copy shared owner credentials into the new routes.

Production promotion and live execution have not been performed. The preview flag remains default off. Live execution is outside this preview's scope.
