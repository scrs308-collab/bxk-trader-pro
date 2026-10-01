# Production Commercial Configuration Gap

Checked against the current Railway production service configuration for `app.bxktraderpro.com`.

## Present in Railway

- `BXK_AUTH_ENABLED`
- `BXK_AUTH_COOKIE_SECURE`
- `BXK_SESSION_SECRET`
- `BXK_BROKER_CREDENTIAL_KEY`
- `SCHWAB_REDIRECT_URI`

## Not currently defined in Railway

### Schwab
- `SCHWAB_CLIENT_ID`
- `SCHWAB_CLIENT_SECRET`

These should not be added until the correct commercial application credentials are issued/confirmed.

### Stripe / subscription
- `BXK_BILLING_ENABLED`
- `BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED`
- `BXK_PUBLIC_APP_URL`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_PRO_MONTHLY`
- `STRIPE_PRICE_PRO_ANNUAL`

The code intentionally defaults billing and subscription enforcement to disabled. Do not enable either control until Stripe products/prices, webhook signing, customer-portal configuration, and end-to-end test-mode billing validation are complete.

## Recommended rollout order

1. Keep `BXK_LIVE_TRADING_ENABLED` under existing owner control.
2. Complete Schwab commercial onboarding.
3. Add approved Schwab production credentials and confirm the exact redirect URI.
4. Configure Stripe products/prices in test mode.
5. Add Stripe test credentials and price IDs.
6. Set `BXK_PUBLIC_APP_URL=https://app.bxktraderpro.com`.
7. Enable `BXK_BILLING_ENABLED=true` while leaving subscription enforcement off.
8. Validate checkout, webhook processing, customer portal, renewal failure, and cancellation.
9. Configure production Stripe credentials and prices.
10. Turn on subscription enforcement only after existing approved users have valid entitlements or manual access overrides.

## Important

This document records variable-name presence only. Secret values were not retrieved or copied into source control.
