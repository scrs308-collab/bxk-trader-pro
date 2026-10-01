# Schwab Trader API Commercial Submission Draft

This document is a working response package for Schwab Trader API Commercial onboarding. It is written to answer the information Schwab has already requested about BXK Trader Pro without overstating any unapproved Schwab capability.

## Company and application

**Company:** BXK Capital Trading LLC  
**Application:** BXK Trader Pro  
**Public website:** https://bxktraderpro.com  
**Application URL:** https://app.bxktraderpro.com

**Primary contact:** [Insert final commercial contact name and email used for Schwab onboarding]

## Product summary

BXK Trader Pro is a browser-based options trading decision-support platform for self-directed traders.

The application combines:

- Market context and volatility information
- SPX options trade construction
- Defined-risk strategy analysis
- Position monitoring
- Risk alerts and optional SMS alerts
- Trade journaling and performance review
- Per-user brokerage connections
- Subscription and account-access controls

BXK Trader Pro is intended to help users organize information and manage their own trading workflow. Users remain responsible for reviewing brokerage information, order details, risk, and account restrictions.

## Use cases for Schwab self-directed clients

The intended Schwab integration allows an authenticated BXK Trader Pro user to connect the user's own Schwab brokerage account through the Schwab-authorized authentication flow.

Subject to the final commercial product, approved scopes, and Schwab requirements, the application may use authorized Schwab data to support:

1. Viewing authorized brokerage account information
2. Viewing balances and buying-power information
3. Viewing open positions
4. Viewing order and order-status information where included in the approved API scope
5. Selecting an authorized Schwab account as the user's BXK account-data source
6. Using the authorized account information within BXK position-monitoring and risk-management workflows

The current commercial-readiness implementation treats Schwab as an account-data integration. It does not represent Schwab order execution as generally available.

## Order-entry capability

BXK Trader Pro includes trade-construction and order-workflow capabilities.

Current production execution capability is separated from account-data connectivity and remains permission-controlled by user.

For the Schwab commercial integration:

- Schwab is currently implemented as a read-only/account-data path for commercial review.
- BXK will not advertise or enable Schwab order-entry capability unless the final Schwab commercial approval, scopes, and applicable agreements permit it.
- If Schwab order entry is approved in the future, users would remain responsible for reviewing the symbol, strategy, expiration, strikes, quantity, order type, price, and account before submission.
- Schwab brokerage records would remain authoritative for acceptance, routing, fill status, and brokerage-account state.

## Expected users

Preliminary launch estimate:

- Initial controlled rollout: approximately 10-25 users
- First-year target: approximately 50-100 users

These are planning estimates and may change based on adoption, onboarding pace, broker approval, and commercial rollout.

## Account authorization

BXK users authenticate to BXK Trader Pro with their own application accounts.

Broker authorization is separate from BXK login.

For Schwab:

- The user initiates the Schwab connection from BXK Trader Pro.
- The user is redirected to the Schwab-authorized authentication/consent workflow.
- The user authorizes access to supported Schwab accounts.
- BXK stores the resulting authorization tokens in encrypted form.
- BXK does not request the user's Schwab website password.
- Broker connections are associated with the authenticated BXK user.

## Per-user controls

BXK Trader Pro includes:

- Authenticated BXK user accounts
- Per-user broker authorization
- Per-user account selection
- Per-user Broker Connect permission
- Per-user live-trading permission
- Subscription/access controls
- Password-change controls
- SMS opt-in controls
- Owner administration of approved beta users

A broker connection does not automatically enable live trading.

## Disconnect behavior

BXK Trader Pro includes a user-controlled Schwab disconnect action.

When used, BXK removes the locally stored Schwab authorization tokens and linked account metadata for that BXK user.

Any separate Schwab-side revocation process will follow the final approved commercial API workflow and Schwab requirements.

## Security

Relevant controls include:

- Encrypted broker-token storage
- Per-user broker-account isolation
- Account-number masking in customer-facing views
- OAuth/delegated authorization where supported
- Separate account-data and execution permissions
- Owner-controlled Broker Connect permissions
- Owner-controlled live-trading permissions
- Automated regression tests for user isolation
- Automated PostgreSQL migration validation
- CI checks against common committed-secret formats

## Privacy and customer support

Public customer pages include:

- Privacy Policy
- Terms and Conditions
- Risk disclosures
- Security information
- Support workflow
- Access-request workflow

BXK support instructs users not to submit brokerage passwords, access tokens, refresh tokens, API secrets, full brokerage account numbers, Social Security numbers, or payment-card numbers.

## Subscription model

BXK Trader Pro contains account-level subscription controls and Stripe billing infrastructure for monthly/annual hosted checkout and billing management.

Public prices are not being represented as final until BXK completes commercial rollout decisions and billing configuration.

Subscription access does not guarantee that every broker capability is available for every brokerage account.

## RIA / advisory status

**Owner/compliance confirmation required before submission.**

Suggested factual response format after confirmation:

> BXK Trader Pro is software for self-directed traders and does not provide individualized investment-advisory services. [Insert the company's confirmed registration/status statement here after legal/compliance review.]

Do not submit a registration-status statement until it has been confirmed by the owner and qualified counsel.

## Reviewer access

A controlled reviewer account can be created for Schwab.

Reviewer safeguards:

- Dedicated reviewer account
- No connection to the owner's personal brokerage account
- No live-trading permission by default
- Broker Connect disabled until specifically needed for review
- No personal SMS number
- Password change required on first login
- Controlled subscription access
- Reviewer credentials delivered separately from source control

## Suggested reviewer walkthrough

1. Visit https://bxktraderpro.com
2. Review Product, Security, Subscription, Privacy, Terms, Risk Disclosure, and Support
3. Open the BXK application
4. Sign in using the dedicated reviewer account
5. Review dashboard and trade-construction workflow
6. Review Position Monitor
7. Review Account & Trading Status
8. Review per-user Broker Connect controls
9. Demonstrate Schwab authorization only when approved commercial credentials are configured
10. Show masked authorized account information
11. Show user-controlled Schwab disconnect
12. Review the support and access-request workflows
13. Review Commercial Readiness status

## Items still awaiting external/final confirmation

- Schwab commercial approval
- Final Schwab production client ID and client secret
- Final approved Schwab scopes
- Exact production redirect URI confirmation
- Any Schwab-specific authorization-revocation requirements
- Final public subscription pricing
- Final attorney/compliance review of public commercial language
- Confirmed company RIA/advisory registration status statement
