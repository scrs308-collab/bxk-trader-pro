import unittest
from unittest.mock import Mock

from staging_certification import preflight


class CertificationAccessTests(unittest.TestCase):
    def setUp(self):
        self.env = {"BXK_PREVIEW_MODE": "true", "BXK_LIVE_TRADING_ENABLED": "false",
                    "TASTYTRADE_CERT_BASE_URL": "https://api.cert.tastyworks.com",
                    "TASTYTRADE_CERT_ACCOUNT_NUMBER": "CERT0001",
                    "TASTYTRADE_CERT_CLIENT_ID": "fixture-id",
                    "TASTYTRADE_CERT_CLIENT_SECRET": "fixture-secret",
                    "TASTYTRADE_CERT_REFRESH_TOKEN": "fixture-refresh"}
        self.session = Mock()

    def test_wrong_destination_or_live_flag_blocks_network(self):
        for key, value in [("TASTYTRADE_CERT_BASE_URL", "https://api.tastyworks.com"),
                           ("BXK_LIVE_TRADING_ENABLED", "true")]:
            with self.assertRaises(ValueError):
                preflight({**self.env, key: value}, self.session)
        self.session.post.assert_not_called()
        self.session.get.assert_not_called()

    def test_missing_cert_credentials_never_uses_production_values(self):
        self.env.pop("TASTYTRADE_CERT_CLIENT_SECRET")
        self.env["TASTYTRADE_CLIENT_SECRET"] = "production-fixture"
        with self.assertRaises(ValueError):
            preflight(self.env, self.session)
        self.session.post.assert_not_called()

    def test_auth_failure_redacts_provider_exception(self):
        self.session.post.side_effect = RuntimeError("fixture-secret fixture-refresh")
        with self.assertRaises(RuntimeError) as caught:
            preflight(self.env, self.session)
        self.assertNotIn("fixture-secret", str(caught.exception))
        self.session.get.assert_not_called()

    def test_success_requests_read_only_token_and_only_account_order_gets(self):
        auth = Mock(status_code=200)
        auth.json.return_value = {"access_token": "fixture-access"}
        accounts = Mock(status_code=200)
        accounts.json.return_value = {"data": {"items": [{"account": {"account-number": "CERT0001"}}]}}
        page = Mock(status_code=200)
        page.json.return_value = {"data": {"items": []}, "pagination": {"page-offset": 0, "total-pages": 0}}
        self.session.post.return_value = auth
        self.session.get.side_effect = [accounts, page, page, page]
        report = preflight(self.env, self.session)
        self.assertTrue(report["account_verified"])
        self.assertTrue(report["history_pagination_complete"])
        self.assertFalse(report["submitted"])
        self.assertEqual(self.session.post.call_count, 1)
        self.assertEqual(self.session.post.call_args.args[0], "https://api.cert.tastyworks.com/oauth/token")
        self.assertEqual(self.session.post.call_args.kwargs["json"]["scope"], "read")
        for call in self.session.get.call_args_list:
            self.assertTrue(call.args[0].startswith("https://api.cert.tastyworks.com/"))
            self.assertFalse(call.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
