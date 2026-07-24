# BXK Trader Pro

![Version](https://img.shields.io/badge/version-7.1.0-blue)
![Status](https://img.shields.io/badge/status-Stable-success)
![Python](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Framework-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## Professional SPX Options Trading Platform

BXK Trader Pro is a decision-support platform designed specifically for SPX options traders.

The software combines live market data, volatility analysis, market scoring, expected move calculations, strategy optimization, and intelligent trade recommendations into a single streamlined dashboard.

This project is built for active premium sellers with an emphasis on disciplined risk management and repeatable trading processes.

---

# Current Release

Version **7.1.0**

Status:

**Stable Production Release**

Development Branch:

**v4**

---

# Core Features

### Live Market Data

- SPX
- VIX
- Expected Move
- Live Option Chains

---

### Market Intelligence

- Trade Scoring
- Market Analysis
- Volatility Analysis
- Expected Move

---

### Strategy Engine

- Iron Condor Optimization
- Multi-DTE Optimization
- Wing Optimizer
- Strategy Ranking

---

### Dashboard

- Opportunity Card
- Scanner
- Market Status
- Live Dashboard

---

### Broker Integration

- Tastytrade OAuth
- Live Options Data
- Broker Abstraction Layer

---

# Technology Stack

- Python
- FastAPI
- HTML5
- CSS3
- JavaScript
- GitHub
- Railway

---

# Repository Structure

```
bxk-trader-pro

├── bxk_app/
├── docs/
├── static/
├── requirements.txt
├── README.md
└── server.py
```

---

# Development Workflow

Production

```
main
```

Development

```
v4
```

---

# Documentation

See the **docs** folder for:

- Architecture
- API
- Release Notes
- Trading Logic
- Roadmap
- Change Log

---

# Mission

Build the most practical and intuitive SPX options decision-support platform available.

---

Copyright © 2026

BXK Capital
BXK TRADER PRO DASHBOARD V10
============================

This package replaces the single 1,800+ line dashboard.js with ES modules.

FILES
-----
dashboard.js
config.js
utils.js
market.js
checklist.js
best-trade.js
position.js
position-v10.css

INSTALL
-------
1. Back up your current dashboard.js.

2. Put all seven JavaScript files in the SAME folder where the current
   dashboard.js is located.

3. Replace your existing dashboard script tag with:

   <script type="module" src="/static/js/dashboard.js"></script>

   Keep your actual existing path if it differs. The important change is:
   type="module"

4. Add the optional CSS file after your existing dashboard CSS:

   <link rel="stylesheet" href="/static/css/position-v10.css">

   Again, use the actual path where you place the CSS file.

5. Hard refresh the browser:
   Ctrl + Shift + R

6. Open DevTools > Console. You should see:

   BXK Trader Pro Dashboard - V10

WHAT CHANGED
------------
- Multi-position rendering from data.positions
- Aggregate P/L from data.total_open_pnl
- Legacy fallback from data.position
- No nested functions
- One checklist function
- Position code isolated in position.js
- Best-trade code isolated in best-trade.js
- Market dashboard code isolated in market.js
- Shared helpers isolated in utils.js

ROLLBACK
--------
Restore the old dashboard.js and remove type="module" from the script tag.
