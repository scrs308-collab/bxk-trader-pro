# Pre-Launch Security Audit

## Scope

This audit focuses on the commercial-readiness changes and the production configuration required for broker-connected customer accounts.

## Automated protections

The CI suite now includes a guard against common committed-secret formats, including:

- Stripe live/test secret keys
- Stripe webhook signing secrets
- PEM private keys

Placeholders such as `sk_live_...` remain acceptable documentation because they are not real credentials.

## Production secret handling

Production secret values must remain in Railway or the applicable provider's secret store. They must not be copied into:

- GitHub source
- issue/PR comments
- support requests
- screenshots used for commercial review
- reviewer documentation

## Broker credentials

Per-user broker authorization tokens are stored using the application's broker credential encryption layer.

For Schwab commercial review:

- Use broker authorization rather than collecting the user's Schwab website password.
- Use a dedicated reviewer account.
- Do not connect the owner's personal brokerage account.
- Keep live trading disabled unless the approved commercial workflow specifically requires execution testing.
- Use the Disconnect Schwab control to remove locally stored tokens and linked account metadata after review.

## Customer support

Users are instructed not to submit passwords, tokens, account numbers, Social Security numbers, or payment-card numbers through the support form.

## Railway configuration

The production variable-name audit found the core auth and encryption variable names present, while the Schwab commercial credentials and Stripe production variables remain intentionally unconfigured.

See:
- `docs/production-commercial-config-gap.md`
- `docs/preproduction-commercial-review.md`

## Remaining security work

Before broad commercial launch:

1. Confirm the production broker credential encryption key backup/rotation process.
2. Review Railway service and database access permissions.
3. Confirm production cookie security is enabled.
4. Confirm HTTPS-only public access.
5. Review execution-audit retention and access.
6. Validate disconnect/reconnect behavior in a deployed preview.
7. Confirm Schwab's approved commercial authorization/revocation requirements.
8. Complete attorney/compliance review for customer-facing terms and data handling.
