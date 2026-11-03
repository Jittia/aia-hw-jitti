"""Tests for Moat Momentum v2.0 (Compounder Signal): quarterly rows, signals, winner label, discovery rules.
Spec: docs/specs/2026-11-03-compounder-signal-design.md. Run: .venv/bin/python -m unittest discover tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from test_moat import fact, synthetic  # noqa: E402
from mm_fundamentals import known_as_of  # noqa: E402
from mm_quarterly import lag_q, quarter_flows, ttm_panel  # noqa: E402
from mm_signals import SIGNALS, raw_signals  # noqa: E402
from mm_outcomes import label  # noqa: E402
from mm_discover import combine, keep_rule, run_test, screens  # noqa: E402

COMP = {"compounder": {"train": [2013, 2019], "test": [2020, 2023], "screen_days": ["03-15", "05-15", "08-15", "11-15"],
                       "top_share": 0.10, "keep_years": 5, "pass_multiple": 2.0, "shortlist_size": 25}}

FACTS = ROOT / "data" / "cache" / "mm" / "facts.pkl"


def as_facts(rows: list[dict], base: pd.DataFrame | None = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if base is not None:
        df = pd.concat([base, df], ignore_index=True)
    return df


def quarterly_company() -> pd.DataFrame:
    """synthetic() fiscal years 2020-2022 (calendar years) plus 2022 and 2023 10-Q year-to-date facts."""
    q = []
    for y, (q1, h1, m9) in {2022: (270, 580, 900), 2023: (300, 700, 1080)}.items():
        filed = {1: f"{y}-05-01", 2: f"{y}-08-01", 3: f"{y}-11-01"}
        q += [fact("Revenues", f"{y}-01-01", f"{y}-03-31", q1, filed[1], form="10-Q", kind="Q", accn=f"Q1-{y}"),
              fact("Revenues", f"{y}-01-01", f"{y}-06-30", h1, filed[2], form="10-Q", kind="YTD", accn=f"Q2-{y}"),
              fact("Revenues", f"{y}-01-01", f"{y}-09-30", m9, filed[3], form="10-Q", kind="YTD", accn=f"Q3-{y}")]
    return as_facts(q, synthetic())


def q_rev(df: pd.DataFrame, end: str) -> float:
    return float(df.loc[df["end"] == pd.Timestamp(end), "q_revenue"].iloc[0])


class QuarterRows(unittest.TestCase):
    def test_q4_is_annual_minus_9m(self):
        q = quarter_flows(known_as_of(quarterly_company(), None))
        self.assertAlmostEqual(q_rev(q, "2022-12-31"), 1210 - 900)

    def test_ytd_only_filer(self):
        # Q2 has no 3-month fact: half year (580) − Q1 (270)
        q = quarter_flows(known_as_of(quarterly_company(), None))
        self.assertAlmostEqual(q_rev(q, "2022-06-30"), 580 - 270)
        self.assertAlmostEqual(q_rev(q, "2022-03-31"), 270)

    def test_transition_period_skipped(self):
        # a 10-KT for a 6-month transition period is not a quarter
        f = as_facts([fact("Revenues", "2024-01-01", "2024-06-30", 640, "2024-08-15", form="10-KT", kind="YTD", accn="KT")],
                     quarterly_company())
        q = quarter_flows(known_as_of(f, None))
        self.assertTrue(((q["end"] - q["q_start"]).dt.days.between(80, 100)).all())
        self.assertNotIn(pd.Timestamp("2024-06-30"), set(q["end"]))

    def test_lag_matches_53_week_year(self):
        p = pd.DataFrame({"cik": [1, 1], "end": pd.to_datetime(["2022-06-25", "2023-07-01"]), "x": [1.0, 2.0]})
        self.assertEqual(lag_q(p, "x", 4).iloc[1], 1.0)
        self.assertTrue(np.isnan(lag_q(p, "x", 4).iloc[0]))

    def test_point_in_time(self):
        p = ttm_panel(quarterly_company(), "2023-07-31", 0.21, 0.02)
        self.assertTrue((p["filed"] <= pd.Timestamp("2023-07-31")).all())
        self.assertNotIn(pd.Timestamp("2023-06-30"), set(p["end"]))


def hand_panel() -> pd.DataFrame:
    """One company, 9 quarter ends 2021-06 … 2023-06."""
    ends = pd.to_datetime(["2021-06-30", "2021-09-30", "2021-12-31", "2022-03-31", "2022-06-30", "2022-09-30",
                           "2022-12-31", "2023-03-31", "2023-06-30"])
    n = len(ends)
    p = pd.DataFrame({"cik": 1, "end": ends, "q_revenue": 100.0, "q_gross_margin": 0.40, "q_op_margin": 0.10,
                      "roic_ttm": 0.10, "nopat": 10.0, "ic": 100.0, "fcf_margin": 0.05})
    p.loc[p["end"] == "2022-12-31", "q_revenue"] = 120.0   # growth vs 2021-12: 20%
    p.loc[p["end"] == "2023-06-30", "q_revenue"] = 130.0   # growth vs 2022-06: 30%
    p.loc[p["end"] == "2023-06-30", "q_gross_margin"] = 0.45
    p.loc[p["end"] == "2022-09-30", "q_gross_margin"] = 0.42  # a wrong lag (3 quarters) would give 0.03
    p.loc[p["end"] == "2023-06-30", ["roic_ttm", "nopat", "ic"]] = [0.14, 14.0, 120.0]
    return p.iloc[:n]


class Signals(unittest.TestCase):
    def test_signal_names(self):
        self.assertEqual([n for n, _ in SIGNALS], ["s01_roic_chg", "s02_incr_roic", "s03_gm_chg", "s04_gm_accel",
                         "s05_om_chg", "s08_rev_excess", "s09_rev_accel", "s10_peer_rank_chg", "s11_fcf_margin_chg",
                         "s14_roic_rank"])

    def test_signal_definitions(self):
        r = raw_signals(hand_panel()).set_index("end").loc[pd.Timestamp("2023-06-30")]
        self.assertAlmostEqual(r["s03_gm_chg"], 0.05)
        self.assertAlmostEqual(r["s04_gm_accel"], 0.05 - 0.0)  # change at 2022-12 vs 2021-12 was 0
        self.assertAlmostEqual(r["s09_rev_accel"], 0.30 - 0.20)
        self.assertAlmostEqual(r["s01_roic_chg"], 0.04)
        self.assertAlmostEqual(r["s02_incr_roic"], (14 - 10) / (120 - 100))
        self.assertAlmostEqual(r["rev_growth"], 0.30)

    def test_rebound_flag(self):
        # 12-month revenue more than 20% below its best of the previous 8 quarters = recovering, not compounding
        p = hand_panel().assign(revenue=[400, 420, 440, 300, 250, 260, 300, 330, 360.0])
        r = raw_signals(p).set_index("end")
        self.assertTrue(r.loc[pd.Timestamp("2023-03-31"), "rebound"])       # 330 < 0.8 × 440
        self.assertFalse(r.loc[pd.Timestamp("2023-06-30"), "rebound"])      # 360 ≥ 0.8 × 440 (best of 2021-09 … 2023-03)

    def test_bad_denominators_are_nan(self):
        p = hand_panel()
        p.loc[p["end"] == "2022-06-30", "q_revenue"] = 0.0       # growth base of zero
        p.loc[p["end"] == "2023-06-30", "ic"] = 95.0             # capital shrank: no incremental ROIC
        r = raw_signals(p)
        last = r.set_index("end").loc[pd.Timestamp("2023-06-30")]
        self.assertTrue(np.isnan(last["rev_growth"]))
        self.assertTrue(np.isnan(last["s02_incr_roic"]))
        cols = [c for c in r.columns if c.startswith("s")]
        self.assertFalse(np.isinf(r[cols].to_numpy(dtype=float)).any())


@unittest.skipUnless(FACTS.exists(), "needs data/cache/mm/facts.pkl")
class SignalsRealData(unittest.TestCase):
    def test_universe_matches_v11(self):
        import yaml
        from mm_fundamentals import scoring_table
        from mm_score import score_as_of
        from mm_signals import signals_at
        st = yaml.safe_load((ROOT / "settings.yaml").read_text())
        f, c = pd.read_pickle(FACTS), pd.read_pickle(ROOT / "data" / "cache" / "mm" / "companies.pkl")
        sig = signals_at(f, c, "2016-05-15", st, live=False)
        res = score_as_of(scoring_table(f, "2016-05-15", ttm=False), c, "2016-05-15", st, live=False)["results"]
        self.assertEqual(set(sig["cik"]), set(res.loc[res["in_universe"], "cik"]))
        self.assertTrue(sig[[f"r_{n}" for n, _ in SIGNALS]].stack().between(0, 100).all())


def outcome_company(cik, cagr=0.25, roic=(0.12, 0.12, 0.12, 0.12), gm=(0.40, 0.40), goodwill=(0.0, 0.0),
                    revenue_path=None, years=4):
    ends = pd.date_range("2016-03-31", periods=years, freq="12ME")
    rev = revenue_path or [100 * (1 + cagr) ** i for i in range(years)]
    return pd.DataFrame({"cik": cik, "end": ends, "revenue": rev[:years], "roic_ttm": list(roic)[:years],
                         "gross_margin": [gm[0]] * (years - 1) + [gm[1]], "goodwill": [goodwill[0]] * (years - 1) + [goodwill[1]],
                         "assets": 1000.0})


def outcome(company: pd.DataFrame, peer_cagr: float = 0.0) -> pd.Series:
    panel = pd.concat([company, outcome_company(8, peer_cagr), outcome_company(9, peer_cagr)], ignore_index=True)
    rows = pd.DataFrame({"cik": [company["cik"].iloc[0], 8, 9], "end": pd.Timestamp("2016-03-31"), "industry_group": "SIC 99"})
    return label(panel, rows).set_index("cik").loc[company["cik"].iloc[0]]


class WinnerLabel(unittest.TestCase):
    def test_all_six_pass(self):
        self.assertEqual(outcome(outcome_company(1))["winner"], True)

    def test_cagr_19pct_fails(self):
        self.assertEqual(outcome(outcome_company(1, cagr=0.19))["winner"], False)

    def test_peer_excess_9pt_fails(self):
        self.assertEqual(outcome(outcome_company(1), peer_cagr=0.16)["winner"], False)

    def test_one_down_year_fails(self):
        self.assertEqual(outcome(outcome_company(1, revenue_path=[100, 160, 150, 200]))["winner"], False)

    def test_roic_one_of_three_fails(self):
        self.assertEqual(outcome(outcome_company(1, roic=(0.12, 0.05, 0.05, 0.12)))["winner"], False)

    def test_roic_end_drop_fails(self):
        self.assertEqual(outcome(outcome_company(1, roic=(0.20, 0.15, 0.15, 0.15)))["winner"], False)

    def test_gm_drop_3pt_fails(self):
        self.assertEqual(outcome(outcome_company(1, gm=(0.40, 0.37)))["winner"], False)

    def test_gross_margin_missing_skips_c5(self):
        self.assertEqual(outcome(outcome_company(1, gm=(np.nan, np.nan)))["winner"], True)

    def test_goodwill_30pct_fails(self):
        self.assertEqual(outcome(outcome_company(1, goodwill=(0.0, 300.0)))["winner"], False)

    def test_missing_middle_year_is_nan(self):
        # an untagged 10-Q at +8 quarters is missing data, not a failed company
        c = outcome_company(1)
        c = c[c["end"] != c["end"].iloc[2]]
        self.assertTrue(pd.isna(outcome(c)["winner"]))

    def test_acquired_is_nan(self):
        self.assertTrue(pd.isna(outcome(outcome_company(1, years=3))["winner"]))


def keep_rows(passing: dict[str, int], bottom: set[str] = frozenset()) -> pd.DataFrame:
    """7 training years × 100 companies. For signal n, its top-10% (rank ≥ 90) holds 2 winners in the first
    passing[n] years; in the other years the winners sit in its bottom decile. Signals in `bottom` are mirrored."""
    rows = []
    for yi, y in enumerate(range(2013, 2020)):
        for i in range(100):
            rows.append({"year": y, "screen": f"{y}-05-15", "cik": i, "rank_i": float(i)})
    df = pd.DataFrame(rows)
    df["winner"] = False
    for n, k in passing.items():
        r = df["rank_i"] if n not in bottom else 99 - df["rank_i"]
        df[f"r_{n}"] = r
    for yi, y in enumerate(range(2013, 2020)):
        m = df["year"] == y
        # winners: companies 95 and 96 if A passes this year, else companies 3 and 4
        top = yi < list(passing.values())[0]
        df.loc[m & df["cik"].isin([95, 96] if top else [3, 4]), "winner"] = True
    return df


class Discovery(unittest.TestCase):
    def test_screens(self):
        self.assertEqual(len(screens(COMP, "train")), 28)
        self.assertEqual(screens(COMP, "test")[0], "2020-03-15")
        self.assertEqual(len(screens(COMP, "test")), 16)

    def test_keep_rule_years(self):
        df = keep_rows({"A": 5})
        df["r_B"] = df["rank_i"].where(df["year"] != 2017, 99 - df["rank_i"])  # B: A's pattern but fails one more year
        res = keep_rule(df, COMP, signals=[("A", 1), ("B", 1)])
        self.assertEqual(res["kept"], {"A": 1})
        self.assertAlmostEqual(res["by_year"]["A"][2013]["top_rate"], 0.2)
        self.assertAlmostEqual(res["by_year"]["A"][2013]["base_rate"], 0.02)

    def test_keep_rule_direction(self):
        df = keep_rows({"A": 7, "C": 7, "D": 7}, bottom={"C", "D"})
        res = keep_rule(df, COMP, signals=[("A", 1), ("C", 1), ("D", 0)])
        self.assertEqual(res["kept"], {"A": 1, "D": -1})

    def test_combine_flips_negative(self):
        df = pd.DataFrame({"r_A": [80.0], "r_D": [30.0]})
        self.assertAlmostEqual(combine(df, {"A": 1, "D": -1}).iloc[0], 75.0)

    def test_combine_needs_half(self):
        df = pd.DataFrame({"r_A": [80.0], "r_B": [np.nan], "r_C": [np.nan]})
        self.assertTrue(np.isnan(combine(df, {"A": 1, "B": 1, "C": 1}).iloc[0]))

    def test_test_runs_once(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "discovery.json"
            path.write_text(json.dumps({"kept": {"A": 1}, "test": {"passed": False}}))
            with self.assertRaises(SystemExit):
                run_test(COMP, path, rows=pd.DataFrame())

    def test_train_refuses_after_test(self):
        import json
        import tempfile
        from mm_discover import run_train
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "discovery.json"
            path.write_text(json.dumps({"kept": {"A": 1}, "test": {"passed": False}}))
            with self.assertRaises(SystemExit):
                run_train(COMP, path)
            self.assertIn("test", json.loads(path.read_text()))

    def test_test_refuses_changed_settings(self):
        import json
        import tempfile
        from mm_discover import _fingerprint
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "discovery.json"
            path.write_text(json.dumps({"kept": {"A": 1}, "settings_sha256": _fingerprint({"other": 1})}))
            with self.assertRaises(SystemExit):
                run_test(COMP, path, rows=pd.DataFrame({"r_A": [1.0]}))

    def test_rebound_sensitivity_reported(self):
        import json
        import tempfile
        rows = pd.DataFrame({"screen": "2020-05-15", "year": 2020, "ticker": list("ABCDEFGHIJ"), "name": "x",
                             "r_A": [float(i * 10) for i in range(10)], "winner": [False] * 8 + [True, True],
                             "cagr3": 0.1, "rebound": [False] * 9 + [True]})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "discovery.json"
            from mm_discover import _fingerprint
            path.write_text(json.dumps({"kept": {"A": 1}, "settings_sha256": _fingerprint(COMP)}))
            t = run_test(COMP, path, rows=rows)["test"]
        self.assertAlmostEqual(t["top_rate"], 1.0)                       # top 10% = company J, a winner
        self.assertAlmostEqual(t["excl_rebound"]["top_rate"], 1.0)       # without J the top is I, also a winner
        self.assertEqual(t["excl_rebound"]["n_removed"], 1)


if __name__ == "__main__":
    unittest.main()
