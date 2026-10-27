# Workbench production readiness — 2026-10-27

## Verified in isolated staging
- SPX reference, SPXW quotes, combined-condor results and position review exercised by owner.
- Broker dry-run reconciled four legs, fees, buying power and reserve; no order submitted.
- Simulated confirmation durably recorded and consumed once.
- Railway restart rehearsal passed: interrupted attempt recovered as UNKNOWN; original identifiers retained; one attempt; duplicate rejected with HTTP 409. Receipt: 8bbe68c5-e6fe-4305-af37-a0b81085b1d4.
- Local staging suite: 102 tests plus 8 subtests passed. Offline coverage includes stale/future quotes, missing legs, premium drift, expiry, replay and restart persistence.

## Production integration gates — still pending
1. Preserve the production dashboard separately: production root currently serves static/index.html, also used by staging. Do not promote this branch as-is.
2. Introduce a default-off feature flag and separate workbench page, owner-only for initial validation.
3. Use production session authorization and per-user broker credentials; never copy the staging shared-owner authentication or credentials into multi-user routes.
4. Port read-only quote and dry-run services with per-user risk limits, existing-position overlap checks and session gates. Keep live submission unavailable.
5. Run production dashboard, Position Monitor and user-isolation regression checks, then validate the integrated page in staging.
6. Obtain owner approval for production promotion. Live execution requires a separate reviewed implementation and explicit authorization.

Rehearsal controls remain available under a collapsed Staging safety tests disclosure. Certification recovery stays visible because unresolved states must remain apparent.
