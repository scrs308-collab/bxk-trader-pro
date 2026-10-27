"""Offline broker/quote contract checks; fixtures do not prove live connectivity."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
import staging_order_preview as adapter


class DryRunTests(unittest.TestCase):
    def setUp(self):
        self.order = SimpleNamespace(quantity=1, limit_price=2.9, legs=[
            SimpleNamespace(symbol=f"SPXW  261026{kind}{strike:08d}", action=action)
            for kind, strike, action in [
                ("P", 7550000, "Sell to Open"), ("P", 7540000, "Buy to Open"),
                ("C", 7690000, "Sell to Open"), ("C", 7700000, "Buy to Open")]])
        self.quotes = [{"symbol": leg.symbol, "bid": mid-.05, "ask": mid+.05,
                        "timestamp": datetime.now(timezone.utc).isoformat()}
                       for leg, mid in zip(self.order.legs, [3, 1.5, 2.9, 1.5])]
        self.body = {"data": {
            "order": {"status": "Received", "price": "2.90", "price-effect": "Credit",
                      "order-type": "Limit", "time-in-force": "Day",
                      "legs": [dict(symbol=x.symbol, action=x.action, quantity=1,
                                    **{"instrument-type": "Equity Option"}) for x in self.order.legs]},
            "buying-power-effect": {"change-in-buying-power": "715", "current-buying-power": "20000", "new-buying-power": "19285"},
            "fee-calculation": {"total-fees": "5"}, "warnings": [], "errors": []}}
        env = patch.dict(os.environ, {"TASTYTRADE_ACCOUNT_NUMBER": "TEST0001", "BXK_PREVIEW_MODE": "true",
                                     "BXK_LIVE_TRADING_ENABLED": "false", "BXK_MIN_REMAINING_BUYING_POWER": "15000"})
        env.start()
        self.addCleanup(env.stop)

    def preview(self):
        response = Mock(ok=True)
        response.json.return_value = deepcopy(self.body)
        with patch.object(adapter, "get_quotes", return_value={"quotes": self.quotes}), \
             patch.object(adapter, "_headers", return_value={}), \
             patch.object(adapter.requests, "post", return_value=response) as post:
            result = adapter.preview(self.order)
            self.assertTrue(post.call_args.args[0].endswith("/orders/dry-run"))
            self.assertEqual(post.call_count, 1)
            return result

    def test_matching_quotes_order_and_fee_reconciliation_pass(self):
        result = self.preview()
        self.assertTrue(result["all_checks_pass"])
        self.assertTrue(result["server_quote_verified"])
        self.assertEqual(result["estimated_defined_risk"], 710)
        self.assertEqual(result["unexplained_difference_after_fees"], 0)
        self.assertFalse(result["submitted"])
        self.assertFalse(result["execution_authorized"])

    def test_unexplained_fees_block_confirmation(self):
        self.body["data"]["fee-calculation"]["total-fees"] = "4"
        self.assertFalse(self.preview()["all_checks_pass"])

    def test_broker_changed_order_blocks_confirmation(self):
        self.body["data"]["order"]["legs"][0]["quantity"] = 2
        self.assertFalse(self.preview()["all_checks_pass"])

    def test_unknown_warning_blocks_confirmation(self):
        self.body["data"]["warnings"] = [{"code": "unapproved"}]
        self.assertFalse(self.preview()["all_checks_pass"])

    def test_stale_quotes_never_reach_broker(self):
        self.quotes[0]["timestamp"] = (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
        with patch.object(adapter, "get_quotes", return_value={"quotes": self.quotes}), \
             patch.object(adapter.requests, "post") as post:
            with self.assertRaises(HTTPException) as caught:
                adapter.preview(self.order)
            self.assertEqual(caught.exception.status_code, 409)
            post.assert_not_called()

    def test_changed_premium_never_reaches_broker(self):
        self.quotes[0]["bid"] += 0.50
        self.quotes[0]["ask"] += 0.50
        self.assert_quote_rejected_without_broker()

    def test_missing_leg_never_reaches_broker(self):
        self.quotes.pop()
        self.assert_quote_rejected_without_broker()

    def test_future_quote_never_reaches_broker(self):
        self.quotes[0]["timestamp"] = (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
        self.assert_quote_rejected_without_broker()

    def assert_quote_rejected_without_broker(self):
        with patch.object(adapter, "get_quotes", return_value={"quotes": self.quotes}), \
             patch.object(adapter.requests, "post") as post:
            with self.assertRaises(HTTPException) as caught:
                adapter.preview(self.order)
            self.assertEqual(caught.exception.status_code, 409)
            post.assert_not_called()

    def test_live_flag_never_reaches_broker(self):
        with patch.dict(os.environ, {"BXK_LIVE_TRADING_ENABLED": "true"}), \
             patch.object(adapter.requests, "post") as post:
            with self.assertRaises(HTTPException) as caught:
                adapter.preview(self.order)
            self.assertEqual(caught.exception.status_code, 403)
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()

class RejectionDiagnosticsTests(DryRunTests):
    def test_nested_codes_exposed_without_broker_messages(self):
        from fastapi import HTTPException
        response = Mock(ok=False, status_code=422)
        response.json.return_value = {"error": {"code": "preflight_check_failure", "errors": [
            {"code": "order.invalid_price_increment", "message": "private account data"},
            {"code": "unsafe code with spaces"}]}}
        with patch.object(adapter, "get_quotes", return_value={"quotes": self.quotes}), patch.object(adapter, "_headers", return_value={}), patch.object(adapter.requests, "post", return_value=response):
            with self.assertRaises(HTTPException) as caught:
                adapter.preview(self.order)
        self.assertEqual(caught.exception.detail["broker_detail_codes"], ["order.invalid_price_increment"])
        self.assertNotIn("private account data", str(caught.exception.detail))
