# Schwab Trader API Commercial Readiness

This branch tracks work required to present BXK Trader Pro as a finished commercial product for Schwab Trader API review.

## Public product presentation
- [x] Public product overview page
- [x] Privacy Policy expanded for broker-connected and billing data
- [x] Terms & Conditions expanded for connected services and subscriptions
- [x] SMS opt-in disclosure and consent page
- [ ] Public support/contact information (awaiting final support address)
- [ ] Final subscription pricing presentation
- [ ] Final attorney/compliance review of public claims and disclosures

## Account lifecycle
- [x] Secure sign-in
- [x] Forgot-password workflow
- [x] Password-change workflow
- [x] Production access-request workflow with database persistence
- [ ] Email verification, if required for production rollout
- [ ] Administrative approval workflow documented for commercial review

## Subscription and billing
- [x] Stripe monthly/annual checkout foundation
- [x] Stripe customer portal
- [x] Webhook entitlement synchronization
- [ ] Configure production Stripe price IDs
- [ ] Complete end-to-end test-mode billing validation
- [ ] Confirm cancellation, renewal failure, and entitlement behavior
- [ ] Enable production billing only after validation

## Broker connectivity
- [x] Per-user broker connection architecture
- [x] Tastytrade connectivity
- [x] Schwab callback and connection foundation
- [ ] Complete Schwab commercial onboarding
- [ ] Confirm final Schwab scopes and production redirect URI
- [ ] Verify disconnect/revoke experience
- [ ] Prepare reviewer-safe demo account and workflow
- [ ] Do not advertise Schwab connectivity as generally available before approval

## Security and operational controls
- [x] Authenticated application routes
- [x] Per-user broker access boundaries
- [x] Per-user trading permissions
- [x] SMS consent flow
- [ ] Review secrets/configuration in Railway production environment
- [ ] Confirm encryption-key rotation/recovery procedure
- [ ] Confirm audit logging sufficient for broker connection and trade actions
- [ ] Final production security review

## Schwab reviewer package
- [ ] Public product URL
- [ ] Reviewer/demo account
- [ ] Short product overview
- [ ] Description of Schwab data used
- [ ] Description of order-entry behavior
- [ ] Description of user authentication and authorization
- [ ] Privacy Policy URL
- [ ] Terms URL
- [ ] Support contact
- [ ] Screenshots or short walkthrough, if requested

## Validation
- [x] GitHub Actions pytest workflow added to the PR branch
- [x] Full pytest suite passing on the commercial-readiness PR (862 passed)
- [x] New database migrations validated against temporary PostgreSQL in CI
- [ ] Public customer journey smoke-tested end to end (automated page smoke tests added; deployed review still pending)

## Release rule

Do not merge this branch into production until the public copy, subscription presentation, application-access flow, and broker-review disclosures have been reviewed as one customer-facing experience.
