# Pre-Production Commercial Review

Use this checklist before merging the Schwab/commercial-readiness work into production.

## Application deployment candidate

Source branch:
- `schwab-commercial-readiness`

Production application:
- `https://app.bxktraderpro.com`

Production Railway service currently deploys from:
- `main`

Do not point the production service at the review branch. Use a separate preview service or environment if a deployed visual review is required before merge.

## Automated validation

Required before review:
- Full pytest suite passes
- Alembic migration chain applies successfully to PostgreSQL
- Public-page smoke tests pass
- Owner-only administration tests pass
- Schwab disconnect/user-isolation tests pass
- Commercial-readiness endpoint never exposes secret values

## Public journey

Verify in a deployed preview:

1. Open `/product`
2. Follow **Request Account Access**
3. Submit an access request
4. Sign in as OWNER
5. Open **System**
6. Confirm the request appears in **Access & Support Requests**
7. Mark the request Approved
8. Create a controlled BETA user through User Administration
9. Grant manual subscription access
10. Sign in as that user
11. Confirm first-login password change is required
12. Confirm Broker Connect is disabled until OWNER enables it
13. Confirm live trading remains disabled
14. Confirm SMS remains opt-in
15. Open Billing and verify disabled/unconfigured billing fails safely
16. Submit a Support request
17. Confirm OWNER can resolve/close it

## Schwab journey

Do not use an owner's personal account for external review.

When commercial credentials are available:

1. Confirm exact production redirect URI
2. Configure approved Schwab client ID/secret in Railway
3. Use a controlled reviewer/BETA account
4. Enable Broker Connect only for that account
5. Start Schwab authorization
6. Complete broker authorization
7. Confirm only the reviewer's authorized accounts appear
8. Confirm account numbers are masked in the UI
9. Select an account as the account-data source
10. Confirm Schwab remains read-only unless the approved commercial scope explicitly supports more
11. Use **Disconnect Schwab**
12. Confirm local tokens and linked account metadata are removed
13. Confirm another user's broker connection is unchanged
14. Confirm any separate Schwab-side revocation requirement against the final approved API workflow

## Billing journey

Do not enable subscription enforcement first.

Recommended order:

1. Configure Stripe test-mode secret
2. Configure webhook signing secret
3. Configure monthly/annual price IDs
4. Set `BXK_PUBLIC_APP_URL=https://app.bxktraderpro.com`
5. Enable billing only
6. Test monthly Checkout
7. Test annual Checkout
8. Test Customer Portal
9. Test successful webhook entitlement update
10. Test past-due behavior
11. Test cancellation at period end
12. Test immediate cancellation
13. Confirm existing beta/reviewer users retain intended access
14. Only then consider subscription enforcement

## Production merge gates

Do not merge until:
- PR #4 tests are green
- PR #5 marketing validation is green
- Visual preview has been reviewed
- Schwab public copy accurately reflects approval status
- Final pricing language is approved
- Attorney/compliance review is complete for broad commercial launch
- Production secrets/configuration are ready
- Rollback path is understood
