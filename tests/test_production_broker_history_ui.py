"""Guard the actual deployed dashboard against missing broker-history controls."""
from pathlib import Path


def test_production_dashboard_exposes_broker_history():
    dashboard = Path("static/production-dashboard.html").read_text(encoding="utf-8")
    script = Path("static/dashboard.js").read_text(encoding="utf-8")
    server = Path("bxk_app/main.py").read_text(encoding="utf-8")

    assert 'Path("static/production-dashboard.html").read_text()' in server
    assert 'id="brokerHistorySection"' in dashboard
    assert 'id="brokerHistoryRefresh"' in dashboard
    assert 'id="brokerHistoryStatus"' in dashboard
    assert 'id="brokerHistoryList"' in dashboard
    assert 'id="brokerMatchedContracts"' in dashboard
    assert 'getElementById("brokerMatchedContracts")' in script
    assert 'src="/static/dashboard.js?v=42"' in dashboard
    assert 'getElementById("brokerHistoryRefresh")' in script
    assert 'broker-history?days=30' in script
    assert 'addEventListener("click", loadAllBrokerExecutions)' in script


def test_broker_history_panel_is_inside_live_performance_tab():
    dashboard = Path("static/production-dashboard.html").read_text(encoding="utf-8")
    performance = dashboard.index('id="performanceTab"')
    broker_panel = dashboard.index('id="brokerHistorySection"')
    stop_audit = dashboard.index('id="stopAuditSection"')

    assert performance < broker_panel < stop_audit
