# Commercial Release Rollback Plan

This plan applies to the Schwab/commercial-readiness release.

## Before merge

1. Confirm PR #4 CI is green.
2. Confirm PR #5 marketing validation is green.
3. Record the current production application commit SHA.
4. Record the current marketing-site commit SHA.
5. Confirm the production PostgreSQL backup/restore mechanism is available.
6. Confirm the existing Railway deployment is healthy.
7. Do not rotate or replace existing production secrets as part of the code merge unless separately planned.

## Application rollback

The production Trader Pro service deploys from `main`.

If the new release fails after merge:

1. Stop further commercial configuration changes.
2. Disable new billing/subscription enforcement if either was enabled.
3. Keep live-trading permissions in their prior safe state.
4. Revert the merge commit on `main` rather than force-pushing history.
5. Allow Railway to deploy the revert.
6. Confirm `/health`, login, dashboard, broker status, positions, and order-safety checks.
7. Review Railway runtime logs before reattempting the release.

## Database rollback

The commercial-readiness release adds tables for access requests and support requests.

Prefer an application-code rollback without dropping tables. Leaving unused additive tables in place is safer than destructive schema rollback while investigating an incident.

Only run Alembic downgrade in production when:
- the exact downgrade path has been reviewed,
- a database backup exists,
- no production data in the new tables must be retained,
- and the downgrade is necessary to restore service.

## Marketing rollback

The public site deploys independently from `feature/marketing-site`.

If the marketing release has a problem:

1. Revert the marketing PR merge on `feature/marketing-site`.
2. Allow Railway to redeploy the prior static site.
3. Verify bxktraderpro.com, legal pages, support, and Launch App links.

A marketing rollback does not require rolling back the Trader Pro application.

## Configuration rollback

If a failure is caused by newly enabled commercial settings:

- `BXK_BILLING_ENABLED=false` disables Stripe checkout/session processing.
- `BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED=false` prevents subscription enforcement from blocking BETA access.
- Schwab credentials can be removed/disabled without altering Tastytrade connectivity.
- Per-user Broker Connect and live-trading permissions can remain disabled while troubleshooting.

Do not delete existing customer/account data merely to disable a feature.

## Verification after rollback

Confirm:
- authentication works,
- OWNER access works,
- existing BETA users can sign in as intended,
- Tastytrade production behavior matches the prior release,
- Schwab is not presented as approved if commercial approval is still pending,
- billing does not accidentally accept production payments if the release was rolled back,
- access/support submissions do not expose sensitive data.
