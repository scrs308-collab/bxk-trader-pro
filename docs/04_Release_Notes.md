# Release Notes

## Version 7.1.0

Release Date

July 7, 2026

Status

Stable Production Release

### Features

✓ Scanner Engine

✓ Opportunity Engine

✓ Multi-DTE Optimizer

✓ Dashboard

✓ Live Market Integration

✓ Broker Abstraction

✓ Tastytrade OAuth

This version is permanently frozen.

Future development continues on branch **v4**
BXK Trader Pro UI Milestone
Date: July 23, 2026

Completed:
- Wide Live Position Monitor redesign
- Color-coded live P/L
- Larger trade metrics
- Stop-loss debit and dollar calculation
- Responsive position layout
- Market service extraction
- All affected endpoints verified

Next:
- Add support for multiple open positions
- Create build_position_summaries()
- Render one dashboard card per position
- Add aggregate total open P/L
# BXK Trader Pro Release Notes

---

## Version 2.0 Architecture
Date: July 23, 2026

### Service Layer

- Recommendation Service extracted
- Scanner Service extracted
- Broker Service extracted
- Position Service extracted
- Market Service extracted

### Route Refactor

Routes reduced to thin controllers.

Current routes:

- Health
- Market
- Recommendation
- Broker
- Scanner
- Positions
- Options
- Debug

### Position Monitor

Complete dashboard redesign.

Added:

- Wide horizontal layout
- Large live P/L display
- Green positive P/L
- Red negative P/L
- Broker Values panel
- Risk & Profit panel
- Position Structure panel
- Stop Loss panel
- Progress bar
- Position Coach

### Backend

- Fixed refresh-market endpoint
- Market service extraction complete
- Position service extraction complete

### Status

Stable
Production Ready