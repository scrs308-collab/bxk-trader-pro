import unittest
from bxk_app.debit_strategies import selected_debit_legs, construct_legs

class SelectedDebitTests(unittest.TestCase):
    def setUp(self):
        self.chain = [{"strike": s, "expiration_date": "2026-11-05",
                       "put": f"P{s}", "put_streamer": f"p{s}",
                       "call": f"C{s}", "call_streamer": f"c{s}"}
                      for s in range(7500, 7901, 5)]
        self.strikes = [7615, 7640, 7725, 7750]

    def test_review_retains_contracts_when_market_moves(self):
        # Discovery would move the contracts; selected review must not.
        rebuilt = construct_legs("reverse_iron_condor", self.chain, 7690, 25, 84)
        self.assertNotEqual([leg["strike"] for leg in rebuilt], self.strikes)
        selected = selected_debit_legs("reverse_iron_condor", self.chain,
                                      self.strikes, "2026-11-05", 25)
        self.assertEqual([leg["strike"] for leg in selected], self.strikes)
        self.assertEqual([leg["symbol"] for leg in selected],
                         ["P7615", "P7640", "C7725", "C7750"])

    def test_missing_contract_fails_instead_of_substituting(self):
        chain = [r for r in self.chain if r["strike"] != 7640]
        with self.assertRaises(ValueError):
            selected_debit_legs("reverse_iron_condor", chain, self.strikes, "2026-11-05", 25)

    def test_expiration_and_width_must_match(self):
        for expiry, width in [("2026-11-06", 25), ("2026-11-05", 20)]:
            with self.assertRaises(ValueError):
                selected_debit_legs("reverse_iron_condor", self.chain, self.strikes, expiry, width)

    def test_all_manual_debit_patterns(self):
        for strategy, strikes in [("butterfly", [7650,7675,7700]),
                                  ("debit_call_spread",[7650,7675]),
                                  ("debit_put_spread",[7675,7650])]:
            legs = selected_debit_legs(strategy,self.chain,strikes,"2026-11-05",25)
            self.assertEqual([leg["strike"] for leg in legs],strikes)

if __name__ == "__main__":
    unittest.main()
