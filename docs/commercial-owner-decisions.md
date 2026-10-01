# Commercial Owner Decisions

These items require an explicit business, legal, or external-provider decision. They should not be guessed in code.

## 1. Company advisory / registration status

**Status:** OPEN

Before submitting the Schwab commercial package, confirm the exact factual statement BXK Capital Trading LLC should make regarding RIA / investment-adviser registration status.

Do not infer this from the software's "self-directed trader" positioning.

Final approved wording:
- [ ] Pending owner/counsel confirmation

## 2. Public paid pricing

**Status:** OPEN

Current product availability is intentionally described as invite-only beta.

Before public paid enrollment, define:

- Standard monthly price
- Standard annual price, if offered
- Pro monthly price
- Pro annual price, if offered
- Whether SMS Risk Alerts are Pro-only
- Trial policy, if any
- Refund policy, if any

Do not publish placeholder prices as final customer pricing.

## 3. Schwab commercial credentials

**Status:** EXTERNAL

Await Schwab commercial approval and final production credentials/scopes before configuring:

- Schwab client ID
- Schwab client secret
- Exact production redirect URI
- Approved data/order scopes
- Schwab-side revocation requirements

## 4. Reviewer account recipient

**Status:** OPEN UNTIL SCHWAB ASSIGNS REVIEWER

Reviewer credentials must be delivered outside source control.

The account should remain:
- BETA
- Broker Connect disabled by default
- Live trading disabled
- SMS disabled
- Password change required on first login

## 5. Attorney / compliance review

**Status:** OPEN

Before broad paid launch, have qualified counsel review:

- Terms
- Privacy Policy
- Risk Disclosure
- Marketing claims
- Subscription/cancellation language
- Broker-integration descriptions
- Company advisory / registration status statement

## Current no-decision-needed state

These are already intentionally defined:

- Product access: invite-only beta
- Schwab public status: commercial review pending
- Schwab current app role: account-data/read-only path
- Tastytrade: current execution broker
- Live trading: separate per-user permission
- Reviewer demo: preview-only and disabled by default in production
