"""Regression checks for the isolated staging market-data boundary."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class StagingBoundaryTests(unittest.TestCase):
    def test_staging_preview_syntax(self):
        ast.parse((ROOT / "staging_preview.py").read_text(encoding="utf-8"))

    def test_market_adapter_syntax(self):
        ast.parse((ROOT / "staging_market_data.py").read_text(encoding="utf-8"))

    def test_market_adapter_no_order_operations(self):
        source = (ROOT / "staging_market_data.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        request_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "requests"
        ]
        self.assertTrue(request_calls)
        self.assertTrue(all(node.func.attr in {"get", "post"} for node in request_calls))
        self.assertNotIn("/orders", source)
        self.assertNotIn("/accounts", source)

    def test_staging_order_submission_remains_disabled(self):
        source = (ROOT / "staging_preview.py").read_text(encoding="utf-8")
        self.assertIn('def disabled_api(path: str):', source)
        self.assertNotIn('@app.post("/api/order-submit")', source)
        self.assertIn('"/api/workbench/quotes"', source)


if __name__ == "__main__":
    unittest.main()
