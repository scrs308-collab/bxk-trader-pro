# Schwab Commercial Review Package

## Product
BXK Trader Pro is a browser-based options trading decision-support platform operated by BXK Capital Trading LLC.

Primary product URL:
- `/product`

Authenticated application:
- `/`

Public support:
- `/support`

Privacy:
- `/privacy`

Terms:
- `/terms`

## Intended Schwab integration

The Schwab integration is designed for individual BXK Trader Pro users who choose to connect their own Schwab brokerage accounts through Schwab's approved authorization flow.

The application should not advertise Schwab connectivity as generally available until commercial onboarding and any required Schwab approval are complete.

## Schwab data expected to be used

Subject to Schwab-approved scopes and final commercial configuration, BXK Trader Pro may use broker-provided data such as:

- Account identifiers
- Balances and buying power
- Open positions
- Order information and order status
- Supported market and option data
- Other fields made available within the approved Trader API product

The final list must be reconciled against the scopes Schwab approves for production.

## Authentication and authorization model

BXK Trader Pro users authenticate to BXK with their own application accounts.

Broker access is separate from BXK login. A user's Schwab connection is intended to use Schwab's authorization flow so the user authorizes BXK Trader Pro without sharing Schwab website credentials with BXK.

Broker connections are associated with the authenticated BXK user.

## Order behavior

When order-entry functionality is enabled for an authorized user, BXK Trader Pro can construct an order from the user's selected strategy and settings, present the order details, and use the connected broker integration for the permitted workflow.

Users remain responsible for reviewing the order before submission. Broker records control actual order acceptance, routing, fill status, and brokerage-account state.

Live trading permissions are user-specific and can be restricted independently of broker connection permission.

## User isolation and controls

BXK Trader Pro includes:

- Authenticated user sessions
- Per-user broker connections
- Per-user broker authorization permission
- Per-user live-trading permission
- Subscription/access controls
- Execution audit records
- Password-change controls
- Optional SMS consent records and alerts

## Reviewer account

Create a dedicated reviewer-safe account before submitting the product for Schwab review.

Recommended properties:

- Role: VIEWER or specially controlled BETA account
- No connection to the owner's personal brokerage account
- No production live-trading permission unless specifically needed for review
- No personal SMS number
- Seeded or test-safe application state where practical
- Temporary password requiring change on first login

Record the reviewer username and delivery method separately from source control.

## Reviewer walkthrough

1. Open `/product`.
2. Review Features, Broker Connectivity, Security, Privacy, Terms, and Support.
3. Sign in through `/login`.
4. Show the authenticated Trader Pro dashboard.
5. Show Broker Connect and explain per-user authorization.
6. Show trade construction without submitting a live order unless review specifically requires it.
7. Show Position Monitor and account-isolation behavior.
8. Show Billing and SMS consent as separate optional features.
9. Show the broker disconnect/revoke path.
10. Provide Privacy and Terms URLs again in the reviewer response.

## Items to confirm before submission

- Final production domain and HTTPS
- Final Schwab redirect URI
- Final Schwab scopes
- Reviewer account credentials
- Broker disconnect/revoke behavior
- Production support workflow
- Production billing configuration
- Attorney/compliance review of public terms and disclosures
