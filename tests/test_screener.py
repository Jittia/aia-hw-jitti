"""Tests for the Screener (spec docs/specs/2026-11-04-screener-design.md). Run: .venv/bin/python -m unittest discover tests"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mm_screener import earnings_yield_history, group_series, lags5, risk_measures  # noqa: E402


def gpanel(ic=None, nopat=None, gm=None):
    n = 13
    ends = pd.date_range(end="2026-06-30", periods=n, freq="QE")
    ic = ic or [100.0] * 8 + [130.0, 135, 140, 145, 150]
    nopat = nopat or [10.0] + [12.0] * 11 + [16.0]
    gm = gm or [0.40] * 12 + [0.43]
    return pd.DataFrame({"cik": 1, "end": ends, "revenue": [100.0 * 1.1 ** (i / 4) for i in range(n)],
                         "roic_ttm": 0.15, "ic": ic, "nopat": nopat, "gross_margin": gm})


def risk_row(**kw):
    base = {"clean_oi": 30.0, "interest": 10.0, "debt": 200.0, "cash": 50.0, "da": 10.0, "cfo": 40.0}
    base.update(kw)
    return risk_measures(pd.DataFrame([base])).iloc[0]


class Risk(unittest.TestCase):
    def test_measures_values(self):
        r = risk_row(clean_oi=40.0)
        self.assertAlmostEqual(risk_row()["int_cover"], 3.0)
        self.assertAlmostEqual(r["nd_ebitda"], (200 - 50) / (40 + 10))
        self.assertAlmostEqual(r["cfo_debt"], 0.20)
        self.assertFalse(r["net_cash"])
        self.assertTrue(r["int_tagged"])

    def test_net_cash_flags(self):
        r = risk_row(cash=300.0, debt=100.0)
        self.assertTrue(r["net_cash"])

    def test_negative_ebitda_with_net_debt_is_inf(self):
        r = risk_row(clean_oi=-30.0, da=10.0)
        self.assertTrue(math.isinf(r["nd_ebitda"]))

    def test_no_debt_cfo_debt_nan(self):
        r = risk_row(debt=0.0)
        self.assertTrue(np.isnan(r["cfo_debt"]))

    def test_interest_not_tagged(self):
        r = risk_row(interest=float("nan"))
        self.assertFalse(r["int_tagged"])
        self.assertTrue(np.isnan(r["int_cover"]))


class Groups(unittest.TestCase):
    def test_group_formulas(self):
        g = group_series(gpanel()).iloc[-1]
        self.assertAlmostEqual(g["g2x"], (150 - 130) / 16)
        self.assertAlmostEqual(g["g2y"], (16 - 10) / (150 - 100))
        self.assertAlmostEqual(g["g3y"], 0.03)
        self.assertAlmostEqual(g["g1y"], 0.15 - 0.09)
        self.assertAlmostEqual(g["g4x"], 0.15)
        self.assertAlmostEqual(g["g1x"], g["g3x"])

    def test_g2y_needs_capital_growth(self):
        g = group_series(gpanel(ic=[100.0] * 12 + [105.0])).iloc[-1]
        self.assertTrue(np.isnan(g["g2y"]))

    def test_past_earnings_yield_undoes_split(self):
        panel = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2024-03-31"]), "filed": pd.to_datetime(["2024-05-01"]),
                              "clean_oi": [50.0], "debt": [0.0], "cash": [0.0]})
        px = pd.DataFrame({"AAA": [5.0, 6.0]}, index=pd.PeriodIndex(["2024-03", "2024-04"], freq="M"))
        splits = {"AAA": pd.Series([10.0], index=pd.to_datetime(["2024-06-10"]))}
        cover = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2024-04-20"]), "val": [100.0],
                              "filed": pd.to_datetime(["2024-04-30"])})
        y = earnings_yield_history(panel, pd.Series({1: "AAA"}), px, splits, cover)
        self.assertAlmostEqual(y.iloc[0], 50 / (5 * 10 * 100))

    def _ey(self, cover_val, shares=100.0, revenue=1000.0):
        panel = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2024-03-31"]), "filed": pd.to_datetime(["2024-05-01"]),
                              "clean_oi": [50.0], "debt": [0.0], "cash": [0.0], "shares": [shares], "revenue": [revenue]})
        px = pd.DataFrame({"AAA": [5.0]}, index=pd.PeriodIndex(["2024-03"], freq="M"))
        cover = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2024-04-20"]), "val": [cover_val],
                              "filed": pd.to_datetime(["2024-04-30"])})
        return earnings_yield_history(panel, pd.Series({1: "AAA"}), px, {}, cover).iloc[0]

    def test_past_yield_zero_cover_uses_diluted_shares(self):
        self.assertAlmostEqual(self._ey(0.0, shares=200.0), 50 / (5 * 200))

    def test_past_yield_market_value_out_of_range_is_nan(self):
        self.assertTrue(np.isnan(self._ey(100.0, revenue=1e9)))  # market value 500 = 0.00005% of revenue

    def test_past_yield_split_between_quarter_end_and_share_count(self):
        # 1-for-5 reverse split after the quarter-end but before the cover-page count: adjusted close 5 is already
        # in post-split terms, like the count, so market value = 5 x 100 (not 5 x 0.2 x 100)
        panel = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2025-12-31"]), "filed": pd.to_datetime(["2026-02-05"]),
                              "clean_oi": [50.0], "debt": [0.0], "cash": [0.0]})
        px = pd.DataFrame({"AAA": [5.0]}, index=pd.PeriodIndex(["2025-12"], freq="M"))
        splits = {"AAA": pd.Series([0.2], index=pd.to_datetime(["2026-01-14"]))}
        cover = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2026-02-01"]), "val": [100.0],
                              "filed": pd.to_datetime(["2026-02-05"])})
        y = earnings_yield_history(panel, pd.Series({1: "AAA"}), px, splits, cover)
        self.assertAlmostEqual(y.iloc[0], 50 / (5 * 100))

    def test_five_points_now_first(self):
        p = gpanel()
        p["v"] = np.arange(len(p), dtype=float)
        five = lags5(p, "v").iloc[-1]
        self.assertEqual(list(five), [12.0, 11.0, 10.0, 9.0, 8.0])


if __name__ == "__main__":
    unittest.main()
