"""ADS ratio from a 10-K cover page (market value fix, round 22). Run: .venv/bin/python -m unittest discover tests"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mm_adr import adjust_cover, ads_ratio  # noqa: E402

BEONE = ("<td>American Depositary Shares, each representing 13 Ordinary Shares, par value US$0.0001 per share</td>"
         "<td>ONC</td><td>The Nasdaq Global Select Market</td>")


class Parse(unittest.TestCase):
    def test_digits(self):
        self.assertEqual(ads_ratio(BEONE, "ONC"), 13.0)

    def test_words_and_html_noise(self):
        t = "American&#160;depositary shares (&#8220;ADSs&#8221;), each <b>representing</b> thirteen ordinary shares XYZ Nasdaq"
        self.assertEqual(ads_ratio(t, "XYZ"), 13.0)

    def test_fraction(self):
        t = "American Depositary Shares, each representing one-half of one Class A ordinary share ABC New York Stock Exchange"
        self.assertEqual(ads_ratio(t, "ABC"), 0.5)

    def test_one_to_one_is_no_change(self):
        t = "American Depositary Shares, each representing one ordinary share QQQ Nasdaq"
        self.assertEqual(ads_ratio(t, "QQQ"), 1.0)

    def test_other_ticker_is_not_applied(self):
        # ordinary shares trade as ABC; only a separate ADS line names another symbol
        t = "Ordinary shares ABC Nasdaq. American Depositary Shares, each representing 10 ordinary shares ABCY NYSE"
        self.assertIsNone(ads_ratio(t, "ABC"))

    def test_no_ads(self):
        self.assertIsNone(ads_ratio("Common Stock, $0.01 par value MSFT Nasdaq", "MSFT"))


class Adjust(unittest.TestCase):
    R = {1: {"ratio": 13.0, "filed": "2026-02-26"}}

    def test_cover_divided_by_ratio(self):
        cover = pd.DataFrame({"cik": [1, 2], "end": pd.to_datetime(["2026-07-31"] * 2), "val": [1.3e9, 5e8],
                              "filed": pd.to_datetime(["2026-08-05"] * 2)})
        out = adjust_cover(cover, self.R)
        self.assertEqual(list(out["val"]), [1e8, 5e8])
        self.assertEqual(list(cover["val"]), [1.3e9, 5e8])  # input untouched

    def test_earlier_count_of_same_size_is_adjusted(self):  # BeOne: same 13:1 before the 10-K that states it
        cover = pd.DataFrame({"cik": [1, 1], "end": pd.to_datetime(["2025-10-31", "2026-02-13"]), "val": [1.4e9, 1.43e9],
                              "filed": pd.to_datetime(["2025-11-05", "2026-02-26"])})
        self.assertEqual([round(v) for v in adjust_cover(cover, self.R)["val"]], [round(1.4e9 / 13), 110_000_000])

    def test_count_from_before_a_share_change_is_not_adjusted(self):  # Zai Lab: only a 2021 count, ratio read in 2026
        cover = pd.DataFrame({"cik": [1], "end": pd.to_datetime(["2021-02-26"]), "val": [8.86e7],
                              "filed": pd.to_datetime(["2021-03-01"])})
        self.assertEqual(list(adjust_cover(cover, self.R)["val"]), [8.86e7])


if __name__ == "__main__":
    unittest.main()
