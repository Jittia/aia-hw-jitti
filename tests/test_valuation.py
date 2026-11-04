"""Market value and clean P/E (TTM) shown in the Screener (2026-11-04)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mm_valuation import cover_at, multiples, price_before, valuation  # noqa: E402


def setup():
    latest = pd.DataFrame({"cik": [1, 2, 3, 4], "clean_ni": [50.0, -10.0, 20.0, 5.0], "shares": [10.0, 10.0, 4.0, np.nan],
                           "ticker": ["AAA", "BB.B", "CCC", "DDD"], "revenue": [500.0, 100.0, 80.0, 50.0]})
    px = pd.DataFrame({"AAA": [90.0, 100.0], "BB-B": [5.0, 6.0], "DDD": [1.0, 1.0]},
                      index=pd.PeriodIndex(["2026-09", "2026-10"], freq="M"))
    return latest, px


class Valuation(unittest.TestCase):
    def test_market_value_and_clean_pe(self):
        v = valuation(*setup()).set_index("cik")
        self.assertAlmostEqual(v.loc[1, "mcap"], 100.0 * 10)
        self.assertAlmostEqual(v.loc[1, "pe"], 1000 / 50)
        self.assertEqual(v.loc[1, "price_month"], "2026-10")

    def test_loss_has_no_pe(self):
        v = valuation(*setup()).set_index("cik")
        self.assertAlmostEqual(v.loc[2, "mcap"], 60.0)          # Yahoo ticker uses '-' for '.'
        self.assertTrue(np.isnan(v.loc[2, "pe"]))

    def test_missing_price_or_shares(self):
        v = valuation(*setup()).set_index("cik")
        self.assertTrue(np.isnan(v.loc[3, "mcap"]))
        self.assertTrue(np.isnan(v.loc[4, "mcap"]))


    def test_implausible_share_count_hidden(self):
        # e.g. Waters 2026: SEC share count off by 1,000× → market value 13,900× revenue
        latest, px = setup()
        latest.loc[0, "shares"] = 10.0 * 1e4        # market value 1,000,000 on revenue 500 (2,000×)
        latest.loc[1, "shares"] = 0.0001            # market value 0.0006 on revenue 100 (below 0.2%)
        v = valuation(latest, px).set_index("cik")
        self.assertTrue(np.isnan(v.loc[1, "mcap"]) and np.isnan(v.loc[1, "pe"]))
        self.assertTrue(np.isnan(v.loc[2, "mcap"]))
        self.assertEqual(list(v["check"]), [True, True, False, False])

    def test_cover_page_shares_preferred(self):
        # McDonald's 2026 10-Q tags diluted shares as 712.3 (millions); the cover page says 707,641,531
        latest = pd.DataFrame({"cik": [1, 2], "ticker": ["MCD", "GOOGL"], "clean_ni": [8.787e9, 1e11],
                               "shares": [712.3, 1.21e10], "cover_shares": [707641531.0, np.nan], "revenue": [2.77e10, 4e11]})
        px = pd.DataFrame({"MCD": [258.12], "GOOGL": [285.0]}, index=pd.PeriodIndex(["2026-10"], freq="M"))
        v = valuation(latest, px).set_index("cik")
        self.assertAlmostEqual(v.loc[1, "mcap"], 258.12 * 707641531, delta=1)
        self.assertEqual(v.loc[1, "shares_source"], "cover page")
        self.assertAlmostEqual(v.loc[2, "mcap"], 285.0 * 1.21e10, delta=1)   # no cover count: diluted shares
        self.assertEqual(v.loc[2, "shares_source"], "diluted")

    def test_thin_margin_company_not_hidden(self):
        # a distributor worth 1% of its revenue is real, not a share-count error
        latest = pd.DataFrame({"cik": [1], "ticker": ["DIT"], "clean_ni": [1e7], "shares": [6.4e5], "revenue": [2.8e9]})
        px = pd.DataFrame({"DIT": [45.0]}, index=pd.PeriodIndex(["2026-10"], freq="M"))
        v = valuation(latest, px).iloc[0]
        self.assertAlmostEqual(v["mcap"], 45.0 * 6.4e5)
        self.assertFalse(v["check"])

class PointInTime(unittest.TestCase):
    def test_price_before_uses_previous_month_end(self):
        px = pd.DataFrame({"AAA": [10.0, 11.0, 12.0]}, index=pd.PeriodIndex(["2021-01", "2021-02", "2021-03"], freq="M"))
        self.assertEqual(price_before(px, "2021-03-15")["AAA"], 11.0)

    def test_cover_at_point_in_time(self):
        cov = pd.DataFrame({"cik": [1, 1], "end": pd.to_datetime(["2021-01-20", "2021-04-20"]), "val": [100.0, 120.0],
                            "filed": pd.to_datetime(["2021-02-01", "2021-05-01"])})
        self.assertEqual(cover_at(cov, "2021-03-15")[1], 100.0)


class DailyClose(unittest.TestCase):
    def test_last_close_excludes_run_date(self):
        from mm_market import last_closes
        frame = pd.DataFrame({"AAA": [10.0, 11.0, 12.5]}, index=pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-04"]))
        closes, dates = last_closes(frame, "2026-11-04")       # 12.5 is today's (possibly intraday) bar
        self.assertEqual(closes["AAA"], 11.0)
        self.assertEqual(dates["AAA"], "2026-11-03")


class Multiples(unittest.TestCase):
    def frame(self, **kw):
        base = {"mcap": 1000.0, "debt": 200.0, "cash": 100.0, "revenue": 500.0, "clean_oi": 50.0, "clean_ni": 40.0, "fcf": 30.0}
        base.update(kw)
        return multiples(pd.DataFrame([base])).iloc[0]

    def test_multiples_values(self):
        r = self.frame()
        self.assertAlmostEqual(r["ev"], 1100)
        self.assertAlmostEqual(r["ev_sales"], 2.2)
        self.assertAlmostEqual(r["ev_ebit"], 22)
        self.assertAlmostEqual(r["pe"], 25)
        self.assertAlmostEqual(r["fcf_yield"], 0.03)

    def test_multiples_negative_denominators(self):
        self.assertTrue(np.isnan(self.frame(clean_oi=-5.0)["ev_ebit"]))
        self.assertTrue(np.isnan(self.frame(clean_ni=0.0)["pe"]))
        r = self.frame(mcap=float("nan"))
        self.assertTrue(np.isnan(r[["ev", "ev_sales", "ev_ebit", "pe", "fcf_yield"]].astype(float)).all())


if __name__ == "__main__":
    unittest.main()
