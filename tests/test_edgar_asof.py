"""Point-in-time test for edgar.facts_as_of (spec.md §5 success criteria).

Run after the companyfacts fetch:  .venv/bin/python -m unittest tests/test_edgar_asof.py -v

Expected values were checked by hand against the cited 10-K filings (see prompts.md round 2).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edgar import METRICS, facts_as_of, latest_annual  # noqa: E402

AS_OF = "2019-12-31"

# name: (CIK, expected latest annual revenue visible on AS_OF, period end)
CASES = {
    "AAPL": ("0000320193", 260_174_000_000, "2019-09-28"),
    "NVDA": ("0001045810", 11_716_000_000, "2019-01-27"),
    "LWAY": ("0000814586", 103_350_000, "2018-12-31"),  # small cap; 10-K text: "Net Sales $ 103,350" (thousands)
}


class PointInTime(unittest.TestCase):
    def test_revenue_as_of_2019(self):
        for name, (cik, expected, period_end) in CASES.items():
            with self.subTest(name=name):
                row = latest_annual(cik, "revenue", AS_OF)
                self.assertIsNotNone(row, f"{name}: no annual revenue visible on {AS_OF}")
                print(f"\n{name}: revenue {row['val']:,.0f} USD · period {row['start']}→{row['end']} · "
                      f"{row['form']} filed {row['filed']} · {row['concept']}\n  {row['url']}")
                self.assertLessEqual(row["filed"], AS_OF)
                if expected is not None:
                    self.assertEqual(row["val"], expected)
                    self.assertEqual(row["end"], period_end)

    def test_no_fact_filed_after_as_of(self):
        for name, (cik, _, _) in CASES.items():
            for metric in METRICS:
                with self.subTest(name=name, metric=metric):
                    df = facts_as_of(cik, metric, AS_OF)
                    if not df.empty:
                        self.assertLessEqual(df["filed"].max(), AS_OF)

    def test_filter_actually_removes_later_filings(self):
        # Sanity check: the same lookup with today's date must see more periods than 2019.
        for name, (cik, _, _) in CASES.items():
            with self.subTest(name=name):
                self.assertGreater(len(facts_as_of(cik, "revenue", "2026-11-02")),
                                   len(facts_as_of(cik, "revenue", AS_OF)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
