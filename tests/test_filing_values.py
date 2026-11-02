"""Values found verbatim in the filings by src/verify_filings.py (Day 7, 19/19 matched), kept as regression tests.

Run:  .venv/bin/python -m unittest tests/test_filing_values.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edgar import facts_as_of  # noqa: E402

AS_OF = "2026-11-02"
# (ticker, CIK, metric, period start, period end, value as printed in the filing × unit)
CASES = [
    ("DERM", "0001867066", "revenue", "2026-04-01", "2026-06-30", 18_510_000),         # 10-Q, $ thousands
    ("DERM", "0001867066", "operating_income", "2026-04-01", "2026-06-30", 456_000),
    ("DERM", "0001867066", "cfo", "2026-01-01", "2026-06-30", 1_175_000),              # cash flow is YTD in a 10-Q
    ("TRT", "0000732026", "revenue", "2025-07-01", "2026-06-30", 62_605_000),          # 10-K, fiscal year ends June
    ("TRT", "0000732026", "capex", "2025-07-01", "2026-06-30", 1_741_000),
    ("AAPL", "0000320193", "gross_profit", "2026-03-29", "2026-06-27", 54_770_000_000),  # 10-Q, $ millions
    ("AAPL", "0000320193", "cfo", "2025-09-28", "2026-06-27", 116_996_000_000),
]


class FilingValues(unittest.TestCase):
    def test_values_match_filings(self):
        for t, cik, metric, start, end, expected in CASES:
            with self.subTest(ticker=t, metric=metric):
                f = facts_as_of(cik, metric, AS_OF)
                row = f[(f["start"] == start) & (f["end"] == end)]
                self.assertEqual(len(row), 1, f"{t} {metric} {start}→{end} not found")
                self.assertEqual(row.iloc[0]["val"], expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
