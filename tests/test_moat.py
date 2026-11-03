"""Tests for Moat Momentum cleaning, ratios and scoring. Run: .venv/bin/python -m unittest discover tests

Synthetic tests need no data. Apple tests need data/cache/mm/facts.pkl (python src/mm_extract.py) and are skipped
otherwise. Apple figures are from its 10-K for FY2025 (filed 2025-10-31, accession 0000320193-25-000079).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mm_fundamentals import annual_table, known_as_of  # noqa: E402
from mm_score import combine, industry_groups, rank_in_groups, _consistency, _slope, INDICATORS  # noqa: E402

SETTINGS = yaml.safe_load((ROOT / "settings.yaml").read_text())
FACTS = ROOT / "data" / "cache" / "mm" / "facts.pkl"


def fact(tag, start, end, val, filed, form="10-K", kind="A", accn="A1"):
    return {"cik": 1, "tag": tag, "kind": kind, "start": pd.Timestamp(start) if start else pd.NaT,
            "end": pd.Timestamp(end), "val": val, "filed": pd.Timestamp(filed), "form": form, "accn": accn}


def synthetic() -> pd.DataFrame:
    rows = []
    for y, rev, oi, imp in [(2020, 1000, 100, 0), (2021, 1100, 60, 50), (2022, 1210, 150, 0)]:
        filed = f"{y + 1}-02-15"
        s, e = f"{y}-01-01", f"{y}-12-31"
        rows += [fact("Revenues", s, e, rev, filed), fact("CostOfRevenue", s, e, rev * 0.6, filed),
                 fact("OperatingIncomeLoss", s, e, oi, filed), fact("GoodwillImpairmentLoss", s, e, imp, filed),
                 fact("NetIncomeLoss", s, e, oi * 0.8, filed),
                 fact("NetCashProvidedByUsedInOperatingActivities", s, e, oi, filed),
                 fact("StockholdersEquity", None, e, 500, filed, kind="I"),
                 fact("LongTermDebt", None, e, 200, filed, kind="I"),
                 fact("CashAndCashEquivalentsAtCarryingValue", None, e, 100, filed, kind="I"),
                 fact("Assets", None, e, 1000, filed, kind="I")]
    # FY2021 revenue restated a year later (filed with the FY2022 10-K)
    rows.append(fact("Revenues", "2021-01-01", "2021-12-31", 1150, "2023-02-15", accn="A2"))
    return pd.DataFrame(rows)


class PointInTime(unittest.TestCase):
    def test_restatement_only_after_it_was_filed(self):
        f = synthetic()
        early = known_as_of(f, "2022-06-30")
        late = known_as_of(f, "2023-06-30")
        sel = lambda k: k[(k.tag == "Revenues") & (k.end == "2021-12-31")]["val"].item()  # noqa: E731
        self.assertEqual(sel(early), 1100)
        self.assertEqual(sel(late), 1150)

    def test_no_future_fiscal_years(self):
        d = annual_table(synthetic(), "2022-06-30")
        self.assertEqual(sorted(d["fy"]), [2020, 2021])


class Cleaning(unittest.TestCase):
    def setUp(self):
        self.d = annual_table(synthetic(), None, tax_rate=0.21).set_index("fy")

    def test_impairment_added_back(self):
        self.assertAlmostEqual(self.d.loc[2021, "clean_oi"], 60 + 50)
        self.assertAlmostEqual(self.d.loc[2021, "nopat"], 110 * 0.79)

    def test_gross_profit_from_cost(self):
        self.assertAlmostEqual(self.d.loc[2020, "gross_profit"], 400)

    def test_invested_capital_excess_cash(self):
        # excess cash = 100 − 2% × 1000 = 80 → IC = 500 + 200 − 80
        self.assertAlmostEqual(self.d.loc[2020, "ic"], 620)

    def test_roic_uses_average_capital(self):
        ic20, ic21 = self.d.loc[2020, "ic"], self.d.loc[2021, "ic"]
        self.assertAlmostEqual(self.d.loc[2021, "roic"], self.d.loc[2021, "nopat"] / ((ic20 + ic21) / 2))


class Scoring(unittest.TestCase):
    def test_slope_and_consistency(self):
        y = np.array([[1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [1, np.nan, np.nan, np.nan, 2]], dtype=float)
        s = _slope(y)
        self.assertAlmostEqual(s[0], 1.0)
        self.assertAlmostEqual(s[1], -1.0)
        self.assertTrue(np.isnan(s[2]))  # fewer than 3 points
        c = _consistency(y, 1)
        self.assertEqual(list(c[:2]), [1.0, 0.0])

    def test_peer_group_widens_until_enough_peers(self):
        sic = pd.Series([7372] * 8 + [7371, 7373] + [2834])
        g = industry_groups(sic, 8)
        self.assertEqual(g.iloc[0], "SIC 7372")
        self.assertEqual(g.iloc[8], "SIC 737")  # only 1 in 7371 → widen to 737 (10 members)
        self.assertEqual(g.iloc[10], "all")

    def test_wider_group_includes_narrow_members(self):
        sic = pd.Series([7372] * 8 + [7371])
        g = industry_groups(sic, 8)
        v = pd.DataFrame({"x": list(range(9))})
        p = rank_in_groups(v, g, sic)
        self.assertAlmostEqual(p.loc[8, "x"], 100.0)  # ranked against all 9 in SIC 737, highest value

    def test_blend_and_weights(self):
        cols = {f"{n}_{c}": [60.0] for n, _t, _c, _d, comps in INDICATORS for c in comps}
        pct = pd.DataFrame(cols)
        out = combine(pct, SETTINGS, pd.Series([5.0]))
        self.assertAlmostEqual(out["moat_raw"].item(), 60.0)
        self.assertAlmostEqual(out["moat_score"].item(), 55.0)
        self.assertEqual(out["themes_improving"].item(), 5)
        self.assertTrue(out["moat_strengthening"].item())


@unittest.skipUnless(FACTS.exists(), "needs data/cache/mm/facts.pkl")
class AppleFY2025(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f = pd.read_pickle(FACTS)
        cls.d = annual_table(f[f.cik == 320193], None).set_index("fy")

    def test_reported_values(self):
        r = self.d.loc[2025]
        self.assertEqual(r["revenue"], 416_161_000_000)
        self.assertEqual(r["op_income"], 133_050_000_000)
        self.assertEqual(r["gross_profit"], 195_201_000_000)

    def test_point_in_time_2019(self):
        f = pd.read_pickle(FACTS)
        d = annual_table(f[f.cik == 320193], "2019-12-31")
        self.assertEqual(d["fy"].max(), 2019)


@unittest.skipUnless(FACTS.exists(), "needs data/cache/mm/facts.pkl")
class SpotCheckValues(unittest.TestCase):
    """Values found printed in the 10-K text by src/mm_spotcheck.py (step 4, 2026-11-03). CIKs copied from
    data/cache/mm/run_latest.pkl, not typed from memory (PROJECT_MEMORY rule)."""
    CASES = [  # (ticker, cik, fy, column, value as printed × unit)
        ("MU", 723125, 2026, "revenue", 133_188_000_000), ("MU", 723125, 2026, "op_income", 99_340_000_000),
        ("HXL", 717605, 2025, "revenue", 1_893_900_000), ("HXL", 717605, 2025, "op_income", 171_600_000),
        ("FSS", 277509, 2025, "revenue", 2_180_500_000), ("FSS", 277509, 2025, "op_income", 340_900_000),
        ("COCO", 1482981, 2025, "revenue", 609_780_000), ("COCO", 1482981, 2025, "op_income", 82_532_000),
        ("GSAT", 1366868, 2025, "revenue", 272_986_000), ("GSAT", 1366868, 2025, "op_income", 7_430_000),
    ]

    def test_values_match_10k(self):
        f = pd.read_pickle(FACTS)
        for t, cik, fy, col, expected in self.CASES:
            with self.subTest(ticker=t, column=col):
                d = annual_table(f[f.cik == cik], None).set_index("fy")
                self.assertAlmostEqual(d.loc[fy, col], expected, delta=1)

    def test_business_sale_gain_not_removed(self):
        # TechnipFMC FY2024: $71.3M gain on disposal of Measurement Solutions is printed below operating income
        f = pd.read_pickle(FACTS)
        d = annual_table(f[f.cik == 1681459], None).set_index("fy")
        self.assertAlmostEqual(d.loc[2024, "gains_business"], 71_300_000, delta=1)
        self.assertAlmostEqual(d.loc[2024, "clean_oi"], d.loc[2024, "op_income"] + d.loc[2024, "one_offs"], delta=1)
        self.assertGreater(d.loc[2024, "oi_check_gap"], 0.10)  # (1,157.3 − 956.8) ÷ 1,157.3 = 17%


if __name__ == "__main__":
    unittest.main()
