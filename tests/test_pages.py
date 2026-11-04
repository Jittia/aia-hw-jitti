"""Calculation check: printed page of each value in an Inline XBRL filing
(spec docs/specs/2026-11-04-calculation-check-design.md §6). Run: .venv/bin/python -m unittest discover tests"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mm_pages import contexts, locate, split_pages  # noqa: E402

HTML = (ROOT / "tests" / "fixtures" / "ixbrl_mini.htm").read_text()
REV = "RevenueFromContractWithCustomerExcludingAssessedTax"


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P, cls.C = split_pages(HTML), contexts(HTML)

    def test_page_labels(self):
        self.assertEqual([lab for lab, _ in self.P], ["6", "7", "F-3"])

    def test_footer_styles(self):  # printed page numbers seen in real filings
        from mm_pages import page_label
        cases = {"... Financial Statements. - 3 -": "3", "... statements. -4-": "4", "... Statements. \u200e - 5 -": "5",
                 "... text Page 7": "7", "... text 12 | Acme Corp 2025 Form 10-K": "12", "Acme Corp | 13": "13",
                 "... notes F-3": "F-3", "... Total revenue $ 1,234": "", "... as follows: 21 Table of Contents": "21",
                 "... the year 2025": ""}
        self.assertEqual({k: page_label(k) for k in cases}, cases)

    def test_labels_follow_the_sequence(self):  # a table total at a page end is not a page number
        from mm_pages import trust_labels
        self.assertEqual(trust_labels(["", "1", "2", "3", "99", "5", "6", "F-1", "F-2"]),
                         ["", "1", "2", "3", "", "5", "6", "F-1", "F-2"])
        self.assertEqual(trust_labels(["4", "", "6", "7"]), ["4", "", "6", "7"])

    def test_contexts_skip_dimensions(self):
        self.assertEqual(self.C["c-ytd"], ("2026-01-01", "2026-06-30"))
        self.assertEqual(self.C["c-bs"], (None, "2026-06-30"))
        self.assertNotIn("c-seg", self.C)

    def test_locate_statement_page(self):  # the tagged cell, not the dimensional one or the plain text on page 6
        self.assertEqual(locate(self.P, self.C, REV, 590421000, "2026-01-01", "2026-06-30"), "7")

    def test_negative_value(self):
        self.assertEqual(locate(self.P, self.C, "OperatingIncomeLoss", -13384000, "2023-01-01", "2023-06-30"), "7")

    def test_zero_dash(self):
        self.assertEqual(locate(self.P, self.C, "AssetImpairmentCharges", 0, "2026-01-01", "2026-06-30"), "7")

    def test_millions_and_f_page(self):  # 1,180.9 at scale 6 matches 1,180,887,000 within the shown rounding
        self.assertEqual(locate(self.P, self.C, "CashAndCashEquivalentsAtCarryingValue", 1180887000, None, "2026-06-30"), "F-3")

    def test_unnumbered_page_gives_position(self):  # value found on a page without a printed number
        P = [("", self.P[0][1]), ("", self.P[1][1]), self.P[2]]
        self.assertEqual(locate(P, self.C, REV, 590421000, "2026-01-01", "2026-06-30"), "#2")

    def test_cover_page(self):
        html = ('<xbrli:context id="d"><xbrli:entity></xbrli:entity><xbrli:period><xbrli:instant>2026-07-31</xbrli:instant>'
                '</xbrli:period></xbrli:context><p>Shares outstanding <ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" '
                'contextRef="d" scale="0">48,000,000</ix:nonFraction></p><hr style="page-break-after:always"/><p>Table of Contents</p>')
        from mm_pages import contexts as cx
        self.assertEqual(locate(split_pages(html), cx(html), "EntityCommonStockSharesOutstanding", 48000000, None, "2026-07-31"),
                         "cover page")

    def test_hidden_header_values_are_not_printed(self):  # review: a hidden fact has no printed page
        html = ('<div style="display:none"><ix:header><ix:hidden><ix:nonFraction name="us-gaap:Revenues" contextRef="c" scale="0">5'
                '</ix:nonFraction></ix:hidden><ix:resources><xbrli:context id="c"><xbrli:entity></xbrli:entity><xbrli:period>'
                '<xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context></ix:resources></ix:header></div><p>text 4</p>')
        from mm_pages import contexts as cx
        self.assertIsNone(locate(split_pages(html), cx(html), "Revenues", 5, None, "2026-06-30"))

    def test_not_found_is_none(self):
        self.assertIsNone(locate(self.P, self.C, REV, 1, "2026-01-01", "2026-06-30"))
        self.assertIsNone(locate(self.P, self.C, "GrossProfit", 429836000, "2026-01-01", "2026-06-30"))


class Needed(unittest.TestCase):
    def test_needed_from_audit_lists_every_filed_part(self):
        import json
        import tempfile
        sys.path.insert(0, str(ROOT / "tests"))
        from test_audit import duol_record
        from mm_pages import needed_from_audit
        rec = duol_record()
        rec["mkt"] |= {"cover_accn": "0001628280-26-053603", "cover_end": "2026-07-31", "cover_raw": 48000000.0,
                       "shares_src": "cover page"}
        from mm_audit import export
        with tempfile.TemporaryDirectory() as d:
            export([(1562088, rec)], {}, Path(d))
            need = needed_from_audit(Path(d))
        cik, wanted = need["0001628280-26-053603"]
        self.assertEqual(cik, 1562088)
        self.assertIn(("WeightedAverageNumberOfDilutedSharesOutstanding", "2026-01-01", "2026-06-30", 50080000), wanted)
        self.assertIn(("EntityCommonStockSharesOutstanding", None, "2026-07-31", 48000000), wanted)
        self.assertIn(("RevenueFromContractWithCustomerExcludingAssessedTax", "2025-01-01", "2025-12-31", 1037589000),
                      need["0001628280-26-012494"][1])


class Run(unittest.TestCase):
    def test_failed_download_raises(self):  # review: a 503 must not be cached as "not located"
        from mm_pages import pages_for
        class R:
            def __init__(self, code, text=""): self.status_code, self.text = code, text
        class C:
            def _throttle(self): pass
            class session:
                @staticmethod
                def get(url, timeout=0): return R(503)
        with self.assertRaises(RuntimeError):
            pages_for(1, "0000000001-26-000001", [("Revenues", None, "2026-06-30", 1.0)], C())

    def test_refetches_bad_and_incomplete_cache(self):  # review: truncated file or a newly needed value
        import tempfile
        from mm_pages import run
        need = {"A": (1, [("Revenues", None, "2026-06-30", 1.0), ("Assets", None, "2026-06-30", 2.0)]),
                "B": (2, [("Revenues", None, "2026-06-30", 1.0)])}
        seen = []
        def fake(cik, accn, wanted, client=None):
            seen.append(accn)
            return {"_url": "u", **{f"{t}|{s or ''}|{e}": "7" for t, s, e, _ in wanted}}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "A.json").write_text('{"_url": "u", "Revenues||2026-06-30": "7"}')  # lacks Assets
            (Path(d) / "B.json").write_text('{"_url": "u", "Rev')  # truncated
            found, total = run(need, Path(d), fetch=fake, workers=2, client=object())
        self.assertEqual(sorted(seen), ["A", "B"])
        self.assertEqual((found, total), (3, 3))

    def test_parallel_run_writes_every_filing_and_counts(self):
        import tempfile
        from mm_pages import run
        need = {f"000-{i}": (i, [("Revenues", "2026-01-01", "2026-06-30", 1.0), ("Assets", None, "2026-06-30", 2.0)])
                for i in range(20)}
        def fake(cik, accn, wanted, client=None):
            return {"_url": "u", **{f"{t}|{s or ''}|{e}": ("7" if t == "Revenues" else None) for t, s, e, _ in wanted}}
        with tempfile.TemporaryDirectory() as d:
            found, total = run(need, Path(d), fetch=fake, workers=4, client=object())
            self.assertEqual(len(list(Path(d).glob("*.json"))), 20)
        self.assertEqual((found, total), (20, 40))


@unittest.skipUnless(os.environ.get("MM_NET") == "1", "network test: set MM_NET=1")
class DuolFilings(unittest.TestCase):
    """The DUOL pages found by reading the filings on 2026-11-04."""

    def test_duol_pages(self):
        from mm_pages import pages_for
        q = pages_for(1562088, "0001628280-26-053603", [
            ("CashAndCashEquivalentsAtCarryingValue", None, "2026-06-30", 1180887000),
            ("WeightedAverageNumberOfDilutedSharesOutstanding", "2026-01-01", "2026-06-30", 50080000)])
        self.assertEqual([v for k, v in q.items() if k != "_url"], ["6", "22"])
        k = pages_for(1562088, "0001628280-26-012494", [
            ("RevenueFromContractWithCustomerExcludingAssessedTax", "2025-01-01", "2025-12-31", 1037589000)])
        self.assertEqual([v for x, v in k.items() if x != "_url"], ["84"])
        f3 = pages_for(1562088, "0001562088-25-000168", [
            ("NetCashProvidedByUsedInOperatingActivities", "2025-01-01", "2025-06-30", 196306000)])
        self.assertEqual([v for x, v in f3.items() if x != "_url"], ["9"])


if __name__ == "__main__":
    unittest.main()
