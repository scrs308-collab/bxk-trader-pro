# Architecture

## Data Flow

Live Market Data
        │
        ▼
Market Engine
        │
        ▼
Trade Scoring
        │
        ▼
Opportunity Engine
        │
        ▼
Dashboard
        │
        ▼
Position Engine
        │
        ▼
Trade Journal

---

## Core Modules

Market Engine

Responsible for:

- SPX
- VIX
- Expected Move
- Trend
- Market DNA
- Trade Quality

Opportunity Engine

Responsible for:

- Strike Selection
- Wing Optimization
- Credit
- Probability

Scanner Engine

Responsible for:

- Best setups
- Strategy ranking

AI Coach

Responsible for:

- Recommendations
- Risk alerts
- Position guidance

Journal

Responsible for:

- Logging
- Statistics
- Performance