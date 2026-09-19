# Stripe Billing Setup

BXK Trader Pro uses Stripe-hosted Checkout and the Stripe Customer Portal.
Stripe is the payment authority; the `user_subscriptions` table is the
application authority for Trader Pro access.

## Safety switches

Keep both switches off during initial setup:

```text
BXK_BILLING_ENABLED=false
BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED=false
```

`BXK_BILLING_ENABLED` controls creation and processing of Stripe billing
sessions. `BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED` controls whether a BETA user
without an entitlement is denied trading access. They are intentionally
separate so billing can be tested before access enforcement is activated.

## Required Railway variables

```text
BXK_PUBLIC_APP_URL=https://app.bxktraderpro.com
BXK_STRIPE_PAST_DUE_GRACE_DAYS=3
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_ANNUAL=price_...
```

Store Stripe secrets only as Railway secret variables. Never put them in a
repository file, browser JavaScript, screenshot, or support message.

## Stripe Dashboard setup

1. Create one product named **BXK Trader Pro**.
2. Add one recurring monthly price and one recurring annual price.
3. Copy the two `price_...` IDs into Railway.
4. Configure the Customer Portal to allow payment-method updates, invoice
   history, subscription cancellation, and plan changes only if plan changes
   are intentionally supported.
5. Add a webhook endpoint:

   ```text
   https://app.bxktraderpro.com/api/billing/webhook
   ```

6. Subscribe the endpoint to:

   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `customer.subscription.paused`
   - `customer.subscription.resumed`
   - `invoice.paid`
   - `invoice.payment_failed`

7. Copy the endpoint signing secret into `STRIPE_WEBHOOK_SECRET`.

## Rollout order

1. Deploy the code and run `python -m alembic upgrade head`.
2. Configure Stripe in test mode and set the test keys and price IDs.
3. Set `BXK_BILLING_ENABLED=true` while leaving subscription enforcement off.
4. Test monthly Checkout, annual Checkout, Portal access, renewal failure,
   cancellation at period end, and immediate cancellation.
5. Confirm webhook events show a successful response and the database status
   follows Stripe.
6. Repeat with live-mode products, prices, keys, and webhook endpoint.
7. Grant or verify entitlements for every existing approved beta user.
8. Only then set `BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED=true`.

## Access rules

- OWNER accounts always bypass subscription enforcement.
- An explicit manual deny overrides a Stripe status.
- A valid unexpired manual grant overrides Stripe status.
- Stripe `active` and `trialing` statuses grant access only for a configured
  BXK price ID.
- `past_due` grants temporary access only until the configured grace period
  ends.
- Unknown Stripe price IDs never grant access.
- Canceled, unpaid, paused, and incomplete subscriptions do not grant access.

Webhook event IDs and payload digests are recorded to prevent duplicate
processing. Stripe event timestamps are also recorded so older events cannot
overwrite a newer subscription state.
