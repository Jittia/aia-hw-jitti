"""Quarter derivation and TTM checks (Day 3).

Run:  .venv/bin/python -m unittest tests/test_quarters.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quarters import quarterly, ttm  # noqa: E402

AAPL = "0000320193"


class QuarterDerivation(unittest.TestCase):
    def test_ttm_equals_reported_annual(self):
        # TTM at fiscal year end must equal the 10-K annual figure ($260,174M, FY ended 2019-09-28).
        t = ttm(quarterly(AAPL, "revenue", "2019-12-31")).set_index("end")["ttm"]
        self.assertEqual(t["2019-09-28"], 260_174_000_000)

    def test_q4_matches_filing(self):
        # Apple Q4 FY2019 revenue = $64,040M (10-K filed 2019-10-31).
        q = quarterly(AAPL, "revenue", "2019-12-31").set_index("end")["val"]
        self.assertEqual(q["2019-09-28"], 64_040_000_000)

    def test_cash_flow_quarters_derived_from_ytd(self):
        # 10-Q cash-flow statements are year-to-date only, so most CFO quarters must be derived.
        q = quarterly(AAPL, "cfo", "2019-12-31")
        self.assertIn("derived", set(q["source"]))
        self.assertTrue((q["filed"] <= "2019-12-31").all())


if __name__ == "__main__":
    unittest.main(verbosity=2)
