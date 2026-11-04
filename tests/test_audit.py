"""Calculation check: filed parts of every 12-month figure and the per-company audit record
(spec docs/specs/2026-11-04-calculation-check-design.md §5). Run: .venv/bin/python -m unittest discover tests"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "src"))
from mm_fundamentals import known_as_of, ttm_rows  # noqa: E402

REV = "RevenueFromContractWithCustomerExcludingAssessedTax"


def duol_known() -> pd.DataFrame:
    return known_as_of(pd.read_pickle(FIX / "duol_facts.pkl"), "2026-11-03")


class ExtraFacts(unittest.TestCase):
    def test_extra_rows_reads_htm_instants(self):
        from mm_extract import _extra_rows
        cf = {"facts": {"us-gaap": {"DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent": {"units": {"USD": [
            {"end": "2026-06-30", "val": 132979000, "filed": "2026-08-06", "form": "10-Q", "accn": "0001628280-26-053603"},
            {"end": "2026-06-30", "val": 1, "filed": "2026-08-06", "form": "8-K", "accn": "x"}]}}}}}
        self.assertEqual(_extra_rows(1562088, cf), [(1562088, "DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent",
                                                     "I", None, "2026-06-30", 132979000.0, "2026-08-06", "10-Q", "0001628280-26-053603")])


class TtmParts(unittest.TestCase):
    def test_parts_add_up_and_keep_filings(self):  # DUOL revenue, 12 months to 30 Jun 2026
        from mm_fundamentals import ttm_parts
        p = ttm_parts(duol_known())
        r = p[(p["tag"] == REV) & (p["end"] == "2026-06-30")].iloc[0]
        self.assertEqual((r.a_val, r.val, r.p_val, r.ttm), (1037589000, 590421000, 483008000, 1145002000))
        self.assertEqual((r.a_accn, r.accn, r.p_accn),
                         ("0001628280-26-012494", "0001628280-26-053603", "0001562088-25-000168"))
        self.assertEqual((str(r.a_start.date()), str(r.a_end.date())), ("2025-01-01", "2025-12-31"))
        self.assertEqual((str(r.p_start.date()), str(r.p_end.date())), ("2025-01-01", "2025-06-30"))

    def test_ttm_rows_unchanged(self):
        pd.testing.assert_frame_equal(ttm_rows(duol_known()), pd.read_pickle(FIX / "duol_ttm_rows_before.pkl"))


CACHE = ROOT / "data" / "cache" / "mm"
DUOL = 1562088
DUOL_LIVE = {"ticker": "DUOL", "price": 128.0, "price_date": "2026-11-03", "cover_shares": float("nan"),
             "cover_raw": float("nan"), "ads_ratio": None, "shares": 50080000.0, "mcap": 6410240000.0,
             "ev": 5229353000.0}


def duol_record():
    from mm_audit import company_record
    from mm_fundamentals import ttm_parts
    from mm_quarterly import ttm_panel
    facts = pd.read_pickle(FIX / "duol_facts.pkl")
    k = pd.concat([duol_known(), known_as_of(pd.read_pickle(FIX / "duol_extra.pkl"), "2026-11-03")], ignore_index=True)
    panel = ttm_panel(facts, "2026-11-03", 0.21, 0.02)
    return company_record(DUOL, k, ttm_parts(k), panel[panel["filed"] <= "2026-11-03"], DUOL_LIVE)


def vals(item):
    return [p["val"] for c in item["comps"] if c["used"] for p in c["parts"]]


class Record(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = duol_record()

    def test_points(self):
        self.assertEqual({k: v["end"] for k, v in self.rec["pts"].items()},
                         {"now": "2026-06-30", "q4": "2025-06-30", "q12": "2023-06-30"})
        self.assertTrue(self.rec["pts"]["now"]["ttm"])

    def test_duol_record_matches_hand_built_sheet(self):
        it = self.rec["items"]
        self.assertEqual(vals(it["revenue"]["now"]), [1037589000, 590421000, 483008000])
        self.assertEqual([p["accn"] for p in it["revenue"]["now"]["comps"][0]["parts"]],
                         ["0001628280-26-012494", "0001628280-26-053603", "0001562088-25-000168"])
        self.assertEqual([p["kind"] for p in it["revenue"]["now"]["comps"][0]["parts"]], ["FY", "YTD", "PRIOR"])
        self.assertEqual(it["revenue"]["q12"]["value"], 442389000)
        self.assertEqual(it["equity"]["q12"]["value"], 596405000)
        self.assertEqual(it["cash"]["now"]["value"], 1180887000)
        self.assertEqual(it["debt"]["now"]["value"], 0)
        self.assertEqual(it["htm"]["now"]["value"], 132979000)  # shown, never used in a measure (spec §7)
        self.assertIsNone(it["interest"]["now"]["value"])
        self.assertEqual(self.rec["mkt"]["shares_src"], "diluted")
        sh = it["shares"]["now"]["comps"][0]
        self.assertEqual((sh["tag"], sh["value"]), ("WeightedAverageNumberOfDilutedSharesOutstanding", 50080000))
        self.assertEqual([(p["kind"], p["accn"]) for p in sh["parts"]], [("YTD", "0001628280-26-053603")])

    def test_blocks_equal_panel(self):  # the record re-derives exactly what the dashboard used
        b = self.rec["blocks"]
        self.assertEqual(b["now"]["clean_oi"], 157085000)
        self.assertAlmostEqual(b["now"]["ic"], 251755040, 0)
        self.assertAlmostEqual(b["q4"]["ic"], 18503040, 0)
        self.assertAlmostEqual(b["q12"]["ic"], -73412220, 0)
        self.assertEqual(self.rec["check"], [])

    def test_gross_profit_missing_without_cost_of_revenue(self):  # the tool has no gross profit then
        from mm_audit import items_at, _derived
        w = {"Revenues": 100.0, "OperatingIncomeLoss": 10.0, "revenue": 100.0, "revenue_tag": "Revenues"}
        it = items_at(w, {}, _derived(1, "2026-06-30", w, 0.21, 0.02))
        self.assertIsNone(it["gross_profit"]["value"])
        self.assertEqual([c for c in it["gross_profit"]["comps"] if c["used"]], [])

    def test_10k_point_has_one_fy_part(self):  # Review Focus 1: a 10-K year is one line
        from mm_audit import raw_row
        from mm_fundamentals import ttm_parts
        k = duol_known()
        w, parts = raw_row(k, ttm_parts(k), pd.Timestamp("2025-12-31"), False)
        self.assertEqual(w[REV], 1037589000)
        self.assertEqual([(p["kind"], p["accn"]) for p in parts[REV]], [("FY", "0001628280-26-012494")])


class Recompute(unittest.TestCase):
    def test_recompute_duol(self):  # spec §2: the DUOL numbers checked by hand on 2026-11-04
        from mm_audit import recompute
        m = recompute(duol_record())
        self.assertAlmostEqual(m["g1"][0], 0.3730, 4)
        self.assertAlmostEqual(m["g1"][1], 0.9184, 4)
        self.assertAlmostEqual(m["g2"][0], 1.8796, 4)
        self.assertAlmostEqual(m["g2"][1], 0.5072, 4)
        self.assertAlmostEqual(m["g3"][1], 0.0067, 4)
        self.assertAlmostEqual(m["g4"][1], 0.0300, 4)
        self.assertAlmostEqual(m["nd"], -6.83, 2)
        self.assertIsNone(m["ic"])
        self.assertIsNone(m["cd"])

    def test_compact_duol(self):  # the shape the page reads (window.MM_AUDIT.co[cik])
        from mm_audit import BLOCKS, compact
        c = compact(duol_record())
        self.assertEqual(c["t"], "DUOL")
        self.assertEqual(c["pts"]["now"], ["2026-06-30", True])
        val, comps = c["it"]["revenue"]["now"]
        self.assertEqual(val, 1145002000)
        tag, sign, used, v, parts = comps[0]
        self.assertEqual((tag, sign, used, v), (REV, 1, 1, 1145002000))
        self.assertEqual([p[:2] for p in parts], [["FY", 1037589000], ["YTD", 590421000], ["PRIOR", 483008000]])
        self.assertEqual(c["f"][parts[0][2]][:2], ["0001628280-26-012494", "10-K"])
        self.assertEqual(parts[0][3:], ["2025-01-01", "2025-12-31", ""])  # start, end, page ("" = not looked up yet)
        self.assertEqual(c["b"]["q12"][BLOCKS.index("ic")], -73412220)
        self.assertEqual(c["ck"], [])

    def test_compact_keeps_only_what_the_measures_read(self):
        from mm_audit import compact
        c = compact(duol_record())
        self.assertEqual(set(c["it"]["da"]), {"now"})
        self.assertEqual(set(c["it"]["gross_profit"]), {"now", "q4"})
        self.assertEqual(set(c["it"]["equity"]), {"now", "q4", "q12"})
        unused = [cm for name, bp in c["it"].items() if name != "htm" for x in bp.values() for cm in x[1] if not cm[2]]
        self.assertEqual(unused, [])

    def test_export_shards(self):  # spec §5: over budget -> split by CIK, the page loads the part it needs
        import tempfile
        from mm_audit import export, shard_of
        with tempfile.TemporaryDirectory() as d:
            meta = export([(DUOL, duol_record())], {"as_of": "2026-11-03"}, Path(d))
            files = sorted(p.name for p in Path(d).glob("a*.js"))
            self.assertEqual(files, [f"a{shard_of(DUOL):02d}.js"])
            txt = (Path(d) / files[0]).read_text()
            self.assertTrue(txt.startswith("window.MM_AUDIT = window.MM_AUDIT || {co: {}};"))
            self.assertIn('"1562088":', txt)
            self.assertEqual(meta["n"], 1)

    def test_ads_ratio_only_when_the_count_was_divided(self):  # review: ZLAB's 2021 count was not divided
        from mm_audit import live_rows
        mm = pd.DataFrame({"cik": [1704292], "ticker": ["ZLAB"], "cover_shares": [88592343.0], "shares": [5.0],
                           "mcap": [2500.0], "ev": [2000.0]})
        cov = {1704292: {"accn": "0001193125-21-062279", "end": "2021-02-26", "form": "10-K", "raw": 88592343.0}}
        r = live_rows(mm, pd.Series({"ZLAB": 25.0}, dtype=float), {1704292: {"ratio": 10.0}}, "2026-11-03", cov)[1704292]
        self.assertEqual((r["cover_raw"], r["ads_ratio"]), (88592343.0, None))

    def test_export_skips_unreadable_page_file(self):  # review: one bad cache file must not stop the run
        import tempfile
        from mm_audit import export
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "pages").mkdir()
            (Path(d) / "pages" / "0001628280-26-053603.json").write_text('{"_url": "u", "Reven')
            meta = export([(DUOL, duol_record())], {"as_of": "2026-11-03"}, Path(d) / "out", Path(d) / "pages")
        self.assertEqual(meta["n"], 1)

    def test_live_rows_ads(self):  # Review Focus 3: ADS tickers show the ratio and the count as filed
        from mm_audit import live_rows
        mm = pd.DataFrame({"cik": [1651308], "ticker": ["ONC"], "cover_shares": [100.0], "shares": [5.0],
                           "mcap": [2500.0], "ev": [2000.0]})
        cov = {1651308: {"accn": "0001651308-26-000010", "end": "2026-07-31", "form": "10-Q", "raw": 1300.0}}
        r = live_rows(mm, pd.Series({"ONC": 25.0}, dtype=float), {1651308: {"ticker": "ONC", "ratio": 13.0}}, "2026-11-03", cov)[1651308]  # load_ratios() shape
        self.assertEqual((r["price"], r["cover_shares"], r["ads_ratio"], r["cover_raw"]), (25.0, 100.0, 13.0, 1300.0))
        self.assertEqual((r["price_date"], r["cover_accn"], r["cover_end"]), ("2026-11-03", "0001651308-26-000010", "2026-07-31"))


@unittest.skipUnless((CACHE / "facts.pkl").exists(), "fact store not present")
class AllCompanies(unittest.TestCase):
    """Review Focus 4: for every Screener company, the used parts re-derive the panel's debt, one-offs, cash,
    clean operating income and invested capital at all three points."""

    @classmethod
    def setUpClass(cls):
        import json
        from mm_audit import panel_and_records
        cls.site = json.loads((ROOT / "output" / "data" / "site_data.js").read_text().split("=", 1)[1].rstrip().rstrip(";"))
        ev = {c["cik"]: {"ev": (c.get("mm") or {}).get("ev")} for c in cls.site["companies"]}
        cls.recs = list(panel_and_records("2026-11-03", live=ev))

    def test_every_company_rederives_the_panel(self):
        bad, n = [], 0
        for cik, rec in self.recs:
            n += 1
            if rec["check"]:
                bad.append((cik, rec["check"][:2]))
        self.assertGreater(n, 1500)
        self.assertEqual(bad[:5], [])

    def test_every_company_matches_the_screener(self):  # spec §5: the measures equal what the dashboard shows
        from mm_audit import reconcile
        bad, n = [], 0
        for cik, rec in self.recs:
            n += 1
            d = reconcile(rec, self.site["scr"]["co"][str(cik)], ev_tol=0.001)  # site_data.js keeps EV to 4 significant figures
            if d:
                bad.append((cik, d))
        self.assertGreater(n, 1500)
        self.assertEqual(bad[:5], [])

    def test_export_is_small_and_complete(self):  # spec §5: <= 8 MB, every company, filings referenced by index
        import json
        from mm_audit import compact, shard_of
        out = {str(c): compact(r) for c, r in self.recs}
        parts = {}
        for c, v in out.items():
            parts.setdefault(shard_of(int(c)), {})[c] = v
        self.assertLess(max(len(json.dumps(p, separators=(",", ":"))) for p in parts.values()), 2_000_000)
        d = out["1562088"] if "1562088" in out else next(iter(out.values()))
        self.assertTrue(all(isinstance(f, list) and len(f) == 4 for f in d["f"]))


if __name__ == "__main__":
    unittest.main()


class FrozenPrices(unittest.TestCase):
    def test_reuse_cached_daily_closes(self):  # re-exporting must not move the dashboard to a newer close
        import os
        import tempfile
        from mm_market import prices_daily
        s = pd.Series({"DUOL": 128.0})
        s.attrs.update({"date": "2026-11-03", "retrieved": "2026-11-04"})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "daily.pkl"
            s.to_pickle(p)
            os.environ["MM_REUSE_DAILY"] = "1"
            try:
                out = prices_daily(["DUOL", "GONE"], p)
            finally:
                del os.environ["MM_REUSE_DAILY"]
        self.assertEqual((out["DUOL"], out.attrs["date"]), (128.0, "2026-11-03"))


class RefreshPages(unittest.TestCase):
    def test_refresh_pages_updates_only_page_fields(self):
        import json
        import tempfile
        from mm_audit import export, load_export, refresh_pages
        with tempfile.TemporaryDirectory() as d:
            out, pages = Path(d) / "out", Path(d) / "pages"
            export([(DUOL, duol_record())], {"as_of": "2026-11-03"}, out)
            before = load_export(out)
            pages.mkdir()
            (pages / "0001628280-26-012494.json").write_text(json.dumps(
                {"_url": "u", f"{REV}|2025-01-01|2025-12-31": "84"}))
            refresh_pages(out, pages)
            after = load_export(out)
        part = after["co"]["1562088"]["it"]["revenue"]["now"][1][0][4][0]
        self.assertEqual(part[5], "84")
        part[5] = ""
        self.assertEqual(after, before)
