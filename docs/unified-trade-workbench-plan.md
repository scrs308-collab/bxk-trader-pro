# Unified Trade Workbench integration plan

## Goal
Integrate calculator workbench features into BXK Trader Pro without changing production until tested.

## UI
- Rename Trade Setup to Trade Workbench.
- Preserve existing light/dark theme and top navigation.
- Within Trade Workbench provide BXK Auto, Condor Search, and Custom Builder modes.
- Show strategy results and comparisons before the existing Mission Control details.
- Provide shared Position Analysis and Risk Review for all three modes.
- Require explicit customer confirmation at broker order review; never automatically submit orders.

## Feature mapping
- BXK Auto: existing production strategy engine and scoring, preserved.
- Condor Search: import workbench combined-POP, premium, DTE, wing-width filters and ten-result pagination.
- Custom Builder: import manual strike selection and protection-width controls.
- Position Analysis: import expiration payoff chart, max profit/loss, breakevens and fees.
- Quote handling: reuse production broker data services where permitted; distinguish live, delayed and imported snapshots with timestamps.
- Risk controls: reuse existing account limits and broker buying-power checks.

## Engineering guardrails
1. Audit existing routes, templates, API clients and test suites in both repositories.
2. Reuse existing computation modules instead of duplicating pricing/POP implementations.
3. Preserve the existing Position Monitor, Market Summary, Strategies, Performance, SMS Alerts, Billing and System behavior.
4. Keep the new interface behind a feature flag until regression tests pass.
5. Add unit tests for 4-leg calculations, credit/debit sign, max loss, breakevens, missing quotes, POP availability and quote age.
6. Add integration tests for mode switching, theme persistence, broker connection and explicit order confirmation.
7. Deploy to staging and verify before requesting production approval.

## Compliance review
Keep user-directed filters and neutral strategy comparisons. Review all ranking, scoring, default selection and recommendation language with counsel; UI wording alone does not determine advisory status.

## Status
Planning branch created. No application code changed or deployed yet.
