"""Tests for Moat Momentum v3.0 (Moat Map and Expectation Gap).
Spec: docs/specs/2026-11-04-moat-map-v3-design.md. Run: .venv/bin/python -m unittest discover tests
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mm_revdcf import expectation_gap, implied_growth, model_value  # noqa: E402
from mm_moatmap import classify, leading_at, positions, top25, value_at  # noqa: E402


def qpanel(cik, revenues, roics):
    """Quarter-end panel for one company; lists run oldest → newest."""
    ends = pd.date_range(end="2023-03-31", periods=len(revenues), freq="QE")
    return pd.DataFrame({"cik": cik, "end": ends, "revenue": revenues, "roic_ttm": roics})


def one_date(**cols):
    base = {"cik": [1], "industry_group": ["G"], "x": [0.15], "y": [0.02], "x_4": [0.05], "y_4": [-0.01]}
    base.update({k: [v] for k, v in cols.items()})
    df = pd.DataFrame(base)
    df["d"] = (0.10 - df["x"]).clip(lower=0) + (-df["y"]).clip(lower=0)
    df["d_4"] = (0.10 - df["x_4"]).clip(lower=0) + (-df["y_4"]).clip(lower=0)
    return df


class ReverseDCF(unittest.TestCase):
    def test_model_value_hand_case(self):
        g, m, roic = 0.05, 0.10, 0.20
        expect = sum(100 * 1.05 ** t * m * (1 - g / roic) / 1.09 ** t for t in range(1, 11))
        expect += (100 * 1.05 ** 10 * 1.03 * m * (1 - 0.03 / roic) / 0.06) / 1.09 ** 10
        self.assertAlmostEqual(model_value(g, 100, m, roic), expect, delta=1e-6)

    def test_implied_growth_round_trip(self):
        ev = model_value(0.07, 1000, 0.15 * (1 - 0.21), 0.30)
        self.assertAlmostEqual(implied_growth(ev, 1000, 0.15, 0.30), 0.07, delta=0.001)

    def test_na_cases(self):
        self.assertTrue(math.isnan(implied_growth(1000, 1000, -0.01, 0.30)))   # operating loss
        self.assertTrue(math.isnan(implied_growth(1000, 1000, 0.15, 0.0)))     # ROIC not positive
        self.assertTrue(math.isnan(implied_growth(-5, 1000, 0.15, 0.30)))      # EV not positive
        self.assertTrue(math.isnan(implied_growth(1e12, 1000, 0.15, 0.30)))    # price above anything in range

    def test_first_root_taken(self):
        # a value curve that crosses EV twice (at g = 0.0 and g = 0.3): the lower root is used
        curve = lambda g: 100 + 1000 * g * (0.3 - g) * -1  # noqa: E731
        self.assertAlmostEqual(implied_growth(100, 1, 0.1, 0.2, value_fn=curve), 0.0, delta=0.001)

    def test_gap(self):
        self.assertAlmostEqual(expectation_gap(0.15, 0.08), 0.07)
        self.assertTrue(math.isnan(expectation_gap(0.15, float("nan"))))


class MoatMap(unittest.TestCase):
    def test_x_y_d(self):
        rev = [100.0] * 4 + [110.0] * 4 + [121.0] * 4 + [133.1]
        p = positions(qpanel(1, rev, [0.12] * 13)).iloc[-1]
        self.assertAlmostEqual(p["x"], 0.10, delta=1e-9)
        self.assertAlmostEqual(p["y"], 0.03, delta=1e-9)
        r = one_date(x=0.06, y=-0.02)
        self.assertAlmostEqual(r["d"].iloc[0], 0.06)

    def test_trail_points_a_year_apart(self):
        rev = [100.0 * 1.1 ** (i / 4) for i in range(33)]
        p = positions(qpanel(1, rev, [0.05 + 0.01 * i for i in range(33)])).iloc[-1]
        self.assertAlmostEqual(p["y_t1"], p["y_4"])
        self.assertAlmostEqual(p["y"] - p["y_t5"], 0.01 * 20, delta=1e-9)

    def test_top_right_needs_industry_median(self):
        r = pd.concat([one_date(cik=1, x=0.12, y=0.01), one_date(cik=2, x=0.30, y=0.01)], ignore_index=True)
        c = classify(r)
        self.assertEqual(list(c["top_right"]), [False, True])
        self.assertEqual(list(c["quadrant"]), ["Compounder", "Compounder"])  # chart label ignores the median

    def test_r1_entered(self):
        peer = one_date(cik=9, x=0.01, y=0.0, x_4=0.01, y_4=0.0)  # slower peer: company 1 is above the median
        c = classify(pd.concat([one_date(x=0.15, y=0.02, x_4=0.05, y_4=0.02), peer], ignore_index=True)).iloc[0]
        self.assertTrue(c["r1"])
        c = classify(pd.concat([one_date(x=0.15, y=0.02, x_4=float("nan"), y_4=float("nan")), peer], ignore_index=True)).iloc[0]
        self.assertFalse(c["r1"])

    def test_r2_thresholds(self):
        ok = classify(one_date(x=0.05, y=-0.04, x_4=0.00, y_4=-0.04 - 0.001)).iloc[0]   # d_4 0.141 → d 0.09
        self.assertTrue(ok["r2"])
        small = classify(one_date(x=0.05, y=-0.04, x_4=0.01, y_4=-0.041)).iloc[0]      # fell 0.04
        self.assertFalse(small["r2"])
        far = classify(one_date(x=0.03, y=-0.04, x_4=-0.05, y_4=-0.05)).iloc[0]        # d now 0.11
        self.assertFalse(far["r2"])
        y_down = classify(one_date(x=0.08, y=-0.03, x_4=0.00, y_4=-0.02)).iloc[0]
        self.assertFalse(y_down["r2"])

    def test_top25_order_and_gate(self):
        df = pd.DataFrame({"cik": [1, 2, 3, 4], "r1": True, "gate_removed": [False, True, False, False],
                           "moved": [0.05, 0.50, 0.05, 0.20], "y": [0.01, 0.0, 0.03, 0.0]})
        self.assertEqual(list(top25(df, "r1")["cik"]), [4, 3, 1])


def val_rows(**kw):
    base = {"cik": [1], "ticker": ["AAA"], "revenue": [1000.0], "clean_oi": [150.0], "clean_ni": [110.0], "fcf": [90.0],
            "debt": [100.0], "cash": [50.0], "roic_ttm": [0.30], "shares": [100.0], "x": [0.20], "r1": [True], "r2": [False]}
    base.update({k: [v] for k, v in kw.items()})
    return pd.DataFrame(base)


PX = pd.DataFrame({"AAA": [20.0, 25.0]}, index=pd.PeriodIndex(["2023-03", "2023-04"], freq="M"))
NOCOVER = pd.DataFrame(columns=["cik", "end", "val", "filed"])


class ValueAt(unittest.TestCase):
    def test_market_value_uses_month_before(self):
        r = value_at(val_rows(), "2023-05-15", PX, NOCOVER, live=False).iloc[0]
        self.assertAlmostEqual(r["mcap"], 25.0 * 100)

    def test_missing_price_no_gap(self):
        r = value_at(val_rows(ticker="ZZZ"), "2023-05-15", PX, NOCOVER, live=False).iloc[0]
        self.assertTrue(np.isnan(r["gap"]))
        self.assertFalse(r["r3"])

    def test_r3(self):
        ok = value_at(val_rows(), "2023-05-15", PX, NOCOVER, live=False).iloc[0]   # cheap: EV 2,550 on 1,000 sales
        self.assertGreater(ok["gap"], 0)
        self.assertTrue(ok["r3"])
        dear = value_at(val_rows(x=0.0), "2023-05-15", PX * 4, NOCOVER, live=False).iloc[0]
        self.assertLess(dear["gap"], 0)
        self.assertFalse(dear["r3"])
        neither = value_at(val_rows(r1=False), "2023-05-15", PX, NOCOVER, live=False).iloc[0]
        self.assertFalse(neither["r3"])


class SplitUndo(unittest.TestCase):
    def test_split_factor_after(self):
        from mm_valuation import split_factor_after
        nvda = pd.Series([4.0, 10.0], index=pd.to_datetime(["2021-07-20", "2024-06-10"]))
        self.assertEqual(split_factor_after(nvda, pd.Period("2021-02", "M")), 40.0)
        self.assertEqual(split_factor_after(nvda, pd.Period("2021-07", "M")), 10.0)   # July close is after the 4:1 split
        self.assertEqual(split_factor_after(nvda, pd.Period("2024-06", "M")), 1.0)
        self.assertEqual(split_factor_after(pd.Series(dtype=float), pd.Period("2021-02", "M")), 1.0)

    def test_value_at_undoes_later_split(self):
        # adjusted April 2023 close 25; a 2-for-1 split in 2024 means the actual price then was 50
        splits = {"AAA": pd.Series([2.0], index=pd.to_datetime(["2024-01-10"]))}
        r = value_at(val_rows(), "2023-05-15", PX, NOCOVER, live=False, splits=splits).iloc[0]
        self.assertAlmostEqual(r["mcap"], 50.0 * 100)


class Leading(unittest.TestCase):
    def test_leading_not_reported(self):
        rows = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2023-03-31"]), "revenue": [100.0], "rev_4": [90.0],
                             "rnd": [np.nan], "capex": [5.0]})
        lead = pd.DataFrame(columns=["cik", "tag", "end", "val", "filed"])
        r = leading_at(rows, lead, "2023-05-15").iloc[0]
        self.assertTrue(np.isnan(r["defrev_g"]))
        self.assertTrue(np.isnan(r["backlog_g"]))
        self.assertTrue(np.isnan(r["rnd_int"]))
        self.assertAlmostEqual(r["capex_int"], 0.05)

    def test_backlog_growth_vs_revenue(self):
        rows = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2023-03-31"]), "revenue": [110.0], "rev_4": [100.0],
                             "rnd": [10.0], "capex": [5.0]})
        lead = pd.DataFrame({"cik": [1, 1], "tag": "RevenueRemainingPerformanceObligation",
                             "end": pd.to_datetime(["2022-03-31", "2023-03-31"]), "val": [200.0, 260.0],
                             "filed": pd.to_datetime(["2022-05-01", "2023-05-01"])})
        r = leading_at(rows, lead, "2023-05-15").iloc[0]
        self.assertAlmostEqual(r["backlog_g"], 0.30 - 0.10)
        self.assertAlmostEqual(r["rnd_int"], 10 / 110)


def pass_rows(rates_list: dict, rates_rest: dict, n=100):
    """Synthetic rows: per year, n list members and n rest with the given winner rates."""
    out = []
    for y in (2021, 2022, 2023):
        for i in range(n):
            out.append({"year": y, "r1": True, "winner": i < round(rates_list[y] * n)})
            out.append({"year": y, "r1": False, "winner": i < round(rates_rest[y] * n)})
    return pd.DataFrame(out)


class PassRule(unittest.TestCase):
    def test_passes_rule(self):
        from mm_v3_test import passes
        lose_2022 = passes(pass_rows({2021: 0.10, 2022: 0.01, 2023: 0.08}, {2021: 0.02, 2022: 0.02, 2023: 0.02}), "r1")
        self.assertGreaterEqual(lose_2022["multiple"], 2.0)
        self.assertFalse(lose_2022["passed"])
        ok = passes(pass_rows({2021: 0.04, 2022: 0.04, 2023: 0.04}, {2021: 0.02, 2022: 0.02, 2023: 0.02}), "r1")
        self.assertAlmostEqual(ok["multiple"], 2.0)
        self.assertTrue(ok["passed"])
        low = passes(pass_rows({2021: 0.03, 2022: 0.03, 2023: 0.03}, {2021: 0.02, 2022: 0.02, 2023: 0.02}), "r1")
        self.assertFalse(low["passed"])

    def test_no_outcome_ignored(self):
        from mm_v3_test import passes
        rows = pass_rows({2021: 0.04, 2022: 0.04, 2023: 0.04}, {2021: 0.02, 2022: 0.02, 2023: 0.02})
        extra = pd.DataFrame([{"year": 2021, "r1": True, "winner": np.nan}] * 50)
        self.assertAlmostEqual(passes(pd.concat([rows, extra], ignore_index=True), "r1")["multiple"], 2.0)

    def test_v3_test_runs_once(self):
        import json
        import tempfile
        from mm_v3_test import guard
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "v3_test.json"
            path.write_text(json.dumps({"rules": {}}))
            with self.assertRaises(SystemExit):
                guard(path)

    def test_rebound_flag(self):
        rev = [400, 420, 440, 300, 250, 260, 300, 330, 360.0]
        p = positions(qpanel(1, rev, [0.1] * 9)).set_index("end")
        self.assertTrue(p["rebound"].iloc[-2])     # 330 < 0.8 × 440
        self.assertFalse(p["rebound"].iloc[-1])    # 360 ≥ 0.8 × 440


if __name__ == "__main__":
    unittest.main()
