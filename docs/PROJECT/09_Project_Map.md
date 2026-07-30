# BXK Trader Pro Project Map

Generated: `2026-07-29 21:15:54`

Project health score: **100/100**

> Archive candidates are files requiring review. They are not automatically safe to delete.

## Python entry points

- `bxk_app/main.py`
- `bxk_app/sdk_dxlink_test.py`
- `bxk_app/sdk_test.py`
- `server.py`
- `tools/api_client.py`
- `tools/backup.py`
- `tools/bxk.py`
- `tools/new_doc.py`
- `tools/new_engine.py`
- `tools/project_audit.py`
- `tools/release.py`
- `tools/version.py`

## Python modules

### `bxk_app/broker_tastytrade.py`

Imported by:
- `bxk_app/option_scanner.py`
- `bxk_app/routes/options.py`
- `bxk_app/services/broker_service.py`
- `bxk_app/services/position_service.py`

Local dependencies:
- `bxk_app/config.py`

### `bxk_app/brokers/__init__.py`

Imported by: none detected.

Local dependencies: none detected.

### `bxk_app/brokers/base.py`

Imported by:
- `bxk_app/brokers/tastytrade.py`

Local dependencies: none detected.

### `bxk_app/brokers/tastytrade.py`

Imported by:
- `bxk_app/market_engine.py`
- `bxk_app/services/broker_service.py`

Local dependencies:
- `bxk_app/brokers/base.py`
- `bxk_app/config.py`

### `bxk_app/config.py`

Imported by:
- `bxk_app/broker_tastytrade.py`
- `bxk_app/brokers/tastytrade.py`
- `bxk_app/live_option_engine.py`
- `bxk_app/sdk_dxlink_test.py`
- `bxk_app/sdk_test.py`
- `bxk_app/tastytrade_client.py`

Local dependencies: none detected.

### `bxk_app/live_option_engine.py`

Imported by:
- `bxk_app/option_scanner.py`
- `bxk_app/scanner_engine.py`
- `bxk_app/services/scanner_service.py`
- `bxk_app/trade_builder.py`

Local dependencies:
- `bxk_app/config.py`

### `bxk_app/main.py`

Imported by:
- `server.py`

Local dependencies:
- `bxk_app/routes/__init__.py`

### `bxk_app/market_data.py`

Imported by:
- `bxk_app/market_engine.py`
- `bxk_app/opportunity_engine.py`
- `bxk_app/routes/debug.py`
- `bxk_app/scoring.py`
- `bxk_app/services/market_service.py`
- `bxk_app/services/position_service.py`
- `bxk_app/trade_builder.py`

Local dependencies: none detected.

### `bxk_app/market_engine.py`

Imported by:
- `bxk_app/routes/debug.py`
- `bxk_app/services/market_service.py`
- `bxk_app/services/position_service.py`
- `bxk_app/services/recommendation_service.py`

Local dependencies:
- `bxk_app/brokers/tastytrade.py`
- `bxk_app/market_data.py`

### `bxk_app/models.py`

Imported by:
- `bxk_app/opportunity_engine.py`
- `bxk_app/scoring.py`

Local dependencies: none detected.

### `bxk_app/opportunity_engine.py`

Imported by:
- `bxk_app/services/recommendation_service.py`

Local dependencies:
- `bxk_app/market_data.py`
- `bxk_app/models.py`
- `bxk_app/wing_optimizer.py`

### `bxk_app/option_scanner.py`

Imported by:
- `bxk_app/scanner_engine.py`
- `bxk_app/services/scanner_service.py`
- `bxk_app/trade_builder.py`

Local dependencies:
- `bxk_app/broker_tastytrade.py`
- `bxk_app/live_option_engine.py`
- `bxk_app/scanner_settings.py`
- `bxk_app/trade_quality.py`

### `bxk_app/position_coach.py`

Imported by:
- `bxk_app/position_monitor.py`

Local dependencies: none detected.

### `bxk_app/position_monitor.py`

Imported by:
- `bxk_app/services/position_service.py`

Local dependencies:
- `bxk_app/position_coach.py`

### `bxk_app/routes/__init__.py`

Imported by:
- `bxk_app/main.py`

Local dependencies:
- `bxk_app/routes/broker.py`
- `bxk_app/routes/debug.py`
- `bxk_app/routes/health.py`
- `bxk_app/routes/market.py`
- `bxk_app/routes/options.py`
- `bxk_app/routes/positions.py`
- `bxk_app/routes/recommendation.py`
- `bxk_app/routes/scanner.py`

### `bxk_app/routes/broker.py`

Imported by:
- `bxk_app/routes/__init__.py`

Local dependencies:
- `bxk_app/services/broker_service.py`

### `bxk_app/routes/debug.py`

Imported by:
- `bxk_app/routes/__init__.py`

Local dependencies:
- `bxk_app/market_data.py`
- `bxk_app/market_engine.py`

### `bxk_app/routes/health.py`

Imported by:
- `bxk_app/routes/__init__.py`

Local dependencies: none detected.

### `bxk_app/routes/market.py`

Imported by:
- `bxk_app/routes/__init__.py`

Local dependencies:
- `bxk_app/services/market_service.py`

### `bxk_app/routes/options.py`

Imported by:
- `bxk_app/routes/__init__.py`

Local dependencies:
- `bxk_app/broker_tastytrade.py`
- `bxk_app/trade_builder.py`

### `bxk_app/routes/positions.py`

Imported by:
- `bxk_app/routes/__init__.py`

Local dependencies:
- `bxk_app/services/position_service.py`

### `bxk_app/routes/recommendation.py`

Imported by:
- `bxk_app/routes/__init__.py`

Local dependencies:
- `bxk_app/services/recommendation_service.py`

### `bxk_app/routes/scanner.py`

Imported by:
- `bxk_app/routes/__init__.py`

Local dependencies:
- `bxk_app/services/scanner_service.py`

### `bxk_app/scanner_engine.py`

Imported by:
- `bxk_app/services/scanner_service.py`
- `bxk_app/wing_optimizer.py`

Local dependencies:
- `bxk_app/live_option_engine.py`
- `bxk_app/option_scanner.py`
- `bxk_app/scanner_settings.py`
- `bxk_app/trade_quality.py`

### `bxk_app/scanner_settings.py`

Imported by:
- `bxk_app/option_scanner.py`
- `bxk_app/scanner_engine.py`
- `bxk_app/trade_quality.py`

Local dependencies: none detected.

### `bxk_app/scoring.py`

Imported by:
- `bxk_app/services/market_service.py`
- `bxk_app/services/recommendation_service.py`
- `bxk_app/services/scanner_service.py`
- `bxk_app/trade_builder.py`

Local dependencies:
- `bxk_app/market_data.py`
- `bxk_app/models.py`
- `bxk_app/trade_quality_engine.py`

### `bxk_app/sdk_dxlink_test.py`

Imported by: none detected.

Local dependencies:
- `bxk_app/config.py`

### `bxk_app/sdk_test.py`

Imported by: none detected.

Local dependencies:
- `bxk_app/config.py`

### `bxk_app/services/__init__.py`

Imported by: none detected.

Local dependencies: none detected.

### `bxk_app/services/broker_service.py`

Imported by:
- `bxk_app/routes/broker.py`

Local dependencies:
- `bxk_app/broker_tastytrade.py`
- `bxk_app/brokers/tastytrade.py`
- `bxk_app/tastytrade_client.py`

### `bxk_app/services/market_service.py`

Imported by:
- `bxk_app/routes/market.py`

Local dependencies:
- `bxk_app/market_data.py`
- `bxk_app/market_engine.py`
- `bxk_app/scoring.py`

### `bxk_app/services/position_service.py`

Imported by:
- `bxk_app/routes/positions.py`

Local dependencies:
- `bxk_app/broker_tastytrade.py`
- `bxk_app/market_data.py`
- `bxk_app/market_engine.py`
- `bxk_app/position_monitor.py`

### `bxk_app/services/recommendation_service.py`

Imported by:
- `bxk_app/routes/recommendation.py`

Local dependencies:
- `bxk_app/market_engine.py`
- `bxk_app/opportunity_engine.py`
- `bxk_app/scoring.py`
- `bxk_app/strategy_ranker.py`
- `bxk_app/trade_builder.py`

### `bxk_app/services/scanner_service.py`

Imported by:
- `bxk_app/routes/scanner.py`

Local dependencies:
- `bxk_app/live_option_engine.py`
- `bxk_app/option_scanner.py`
- `bxk_app/scanner_engine.py`
- `bxk_app/scoring.py`
- `bxk_app/strategy_ranker.py`
- `bxk_app/trade_builder.py`
- `bxk_app/wing_optimizer.py`

### `bxk_app/strategy_ranker.py`

Imported by:
- `bxk_app/services/recommendation_service.py`
- `bxk_app/services/scanner_service.py`

Local dependencies: none detected.

### `bxk_app/tastytrade_client.py`

Imported by:
- `bxk_app/services/broker_service.py`

Local dependencies:
- `bxk_app/config.py`

### `bxk_app/trade_analyzer.py`

Imported by:
- `bxk_app/trade_builder.py`

Local dependencies: none detected.

### `bxk_app/trade_builder.py`

Imported by:
- `bxk_app/routes/options.py`
- `bxk_app/services/recommendation_service.py`
- `bxk_app/services/scanner_service.py`

Local dependencies:
- `bxk_app/live_option_engine.py`
- `bxk_app/market_data.py`
- `bxk_app/option_scanner.py`
- `bxk_app/scoring.py`
- `bxk_app/trade_analyzer.py`

### `bxk_app/trade_quality.py`

Imported by:
- `bxk_app/option_scanner.py`
- `bxk_app/scanner_engine.py`

Local dependencies:
- `bxk_app/scanner_settings.py`

### `bxk_app/trade_quality_engine.py`

Imported by:
- `bxk_app/scoring.py`

Local dependencies: none detected.

### `bxk_app/wing_optimizer.py`

Imported by:
- `bxk_app/opportunity_engine.py`
- `bxk_app/services/scanner_service.py`

Local dependencies:
- `bxk_app/scanner_engine.py`

### `server.py`

Imported by: none detected.

Local dependencies:
- `bxk_app/main.py`

### `tools/api_client.py`

Imported by: none detected.

Local dependencies: none detected.

### `tools/backup.py`

Imported by: none detected.

Local dependencies: none detected.

### `tools/bxk.py`

Imported by: none detected.

Local dependencies: none detected.

### `tools/new_doc.py`

Imported by: none detected.

Local dependencies: none detected.

### `tools/new_engine.py`

Imported by: none detected.

Local dependencies: none detected.

### `tools/project_audit.py`

Imported by: none detected.

Local dependencies: none detected.

### `tools/release.py`

Imported by: none detected.

Local dependencies: none detected.

### `tools/version.py`

Imported by: none detected.

Local dependencies: none detected.

## Python archive candidates

None detected.

## Frontend files

### `static/best-trade.js`

Referenced by:
- `static/dashboard.js`

### `static/checklist.js`

Referenced by:
- `static/dashboard.js`

### `static/coach.js`

Referenced by:
- `static/market.js`

### `static/config.js`

Referenced by:
- `static/best-trade.js`
- `static/dashboard.js`
- `static/position.js`

### `static/dashboard.js`

Referenced by:
- `static/index.html`

### `static/index.html`

Referenced by: none detected.

### `static/market.js`

Referenced by:
- `static/dashboard.js`

### `static/position-v10.css`

Referenced by:
- `static/index.html`

### `static/position.js`

Referenced by:
- `static/dashboard.js`

### `static/style.css`

Referenced by:
- `static/index.html`

### `static/utils.js`

Referenced by:
- `static/best-trade.js`
- `static/checklist.js`
- `static/coach.js`
- `static/dashboard.js`
- `static/market.js`
- `static/position.js`

## Frontend archive candidates

None detected.
