"""Screener page logic (riskPass, groupLists, overlap) run in Node, extracted from output/moat_momentum.html.
Spec docs/specs/2026-11-04-screener-design.md §4–6. Skipped when Node is not installed."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "output" / "moat_momentum.html"
NODE = shutil.which("node")


def _fn(src: str, name: str) -> str:
    m = re.search(r"^function " + name + r"\(.*?^}\n", src, re.S | re.M)
    assert m, name
    return m.group(0)


def run_js(expr: str):
    src = HTML.read_text()
    pre = "const MM = {}; const ok = v => v !== null && v !== undefined && isFinite(v);\n"
    m = re.search(r"^const SECTOR_RANGES = \[.*?^\];\n", src, re.S | re.M)
    code = pre + m.group(0) + "".join(_fn(src, n) for n in ("pctRanks", "groupLists", "overlap", "riskPass", "sectorOf", "ddNotes", "makeWlStore", "buildDeck",
                                                 "auditMeasures", "ddCalcRows", "auditWorkbook",
                                                 "driveErrorText", "auditLinkState")) + \
        f"\nPromise.resolve({expr}).then(v => console.log(JSON.stringify(v)));"
    out = subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


T = "{ic: 3, nd: 3, cd: 0.2}"


@unittest.skipUnless(NODE, "node not installed")
class RiskPass(unittest.TestCase):
    def rp(self, **r):
        base = {"nc": False, "hd": True, "it": True, "ic": 5.0, "nd": 1.0, "cd": 0.5}
        base.update(r)
        return run_js(f"riskPass({json.dumps(base)}, {T})")

    def test_healthy_passes(self):
        self.assertEqual(self.rp(), {"ic": "pass", "nd": "pass", "cd": "pass"})

    def test_net_cash_no_interest_passes_all(self):  # Review Focus 1
        self.assertEqual(self.rp(nc=True, it=False, ic=None, nd=-0.5, cd=0.1), {"ic": "pass", "nd": "pass", "cd": "pass"})

    def test_net_cash_with_low_interest_cover_fails_cover(self):  # spec §4: net cash passes the two DEBT checks only
        self.assertEqual(self.rp(nc=True, ic=-5.0, nd=-0.5, cd=0.1), {"ic": "fail", "nd": "pass", "cd": "pass"})

    def test_missing_values_are_not_tested(self):  # spec §2: a missing value never removes a company as a failure
        self.assertEqual(self.rp(ic=None, nd=None, cd=None), {"ic": "nt", "nd": "nt", "cd": "nt"})

    def test_interest_but_no_debt_tagged_debt_checks_not_tested(self):
        self.assertEqual(self.rp(hd=False, nc=True, ic=4.0, nd=-1.0, cd=None), {"ic": "pass", "nd": "nt", "cd": "nt"})

    def test_no_debt_no_interest_passes_all(self):
        self.assertEqual(self.rp(hd=False, nc=True, it=False, ic=None, nd=-1.0, cd=None), {"ic": "pass", "nd": "pass", "cd": "pass"})

    def test_negative_ebitda_with_net_debt_fails(self):
        self.assertEqual(self.rp(nd=999.0)["nd"], "fail")

    def test_thresholds(self):
        self.assertEqual(self.rp(ic=2.9, nd=3.1, cd=0.19), {"ic": "fail", "nd": "fail", "cd": "fail"})


@unittest.skipUnless(NODE, "node not installed")
class Lists(unittest.TestCase):
    def test_list_rules(self):  # Review Focus 2 and spec §5
        N = [None, None]
        rows = [{"cik": 1, "pts": [[0.2, 0.05], N, N, N, [0.1, 0.0]]}, {"cik": 2, "pts": [[0.2, -0.02], N, N, N, [0.2, -0.05]]},
                {"cik": 3, "pts": [[0.2, -0.02], N, N, N, [0.2, 0.0]]}, {"cik": 4, "pts": [[0.05, 0.05], N, N, N, [0.0, 0.05]]},
                {"cik": 5, "pts": [[0.3, 0.10], N, N, N, N]}, {"cik": 6, "pts": [[0.2, -0.03], N, N, N, N]},
                {"cik": 7, "pts": [N, N, N, N, N]}]
        L = run_js(f"(() => {{ const L = groupLists({json.dumps(rows)}, [0.1, 0]); return {{top: L.top.map(r => r.cik), upY: L.upY.map(r => r.cik), upX: L.upX.map(r => r.cik), shown: L.shown, missing: L.missing}}; }})()")
        self.assertEqual(L, {"top": [5, 1], "upY": [2], "upX": [4], "shown": 6, "missing": 1})

    def test_overlap_ranks_by_group_count(self):
        ov = run_js("overlap({g1: {top: [{cik: 5, pct: 90}, {cik: 1, pct: 50}]}, g2: {top: [{cik: 1, pct: 70}]}}, 'top').map(e => [e.cik, e.count, e.pct])")
        self.assertEqual(ov, [[1, 2, 60], [5, 1, 90]])


@unittest.skipUnless(NODE, "node not installed")
class Sectors(unittest.TestCase):
    def test_sic_to_sector(self):  # our approximate mapping from SEC SIC codes to 11 heatmap-style sectors
        cases = {7372: "Technology", 3674: "Technology", 3571: "Technology", 2834: "Health Care", 3841: "Health Care",
                 8062: "Health Care", 1311: "Energy", 2911: "Energy", 4911: "Utilities", 4953: "Industrials",
                 5331: "Consumer Staples", 2086: "Consumer Staples", 5812: "Consumer Discretionary",
                 3711: "Consumer Discretionary", 7011: "Consumer Discretionary", 4813: "Communication Services",
                 7812: "Communication Services", 6798: "Real Estate", 6022: "Financials", 2821: "Materials",
                 1040: "Materials", 3721: "Industrials", 4512: "Industrials", 9995: "Other"}
        got = run_js(f"Object.fromEntries({json.dumps(list(cases))}.map(s => [s, sectorOf(s)]))")
        self.assertEqual({int(k): v for k, v in got.items()}, cases)


def ddrow(**kw):
    N = [None, None]
    r = {"end": "2026-06-30", "ic": 8.0, "nd": 1.0, "cd": 0.5, "nc": False, "it": True, "hd": True,
         "g1": [[0.2, 0.25], [0.19, 0.24], [0.18, 0.22], [0.17, 0.21], [0.16, 0.2]],
         "g2": [[0.8, 0.3], [0.7, 0.28], N, N, [0.6, 0.25]],
         "g3": [[0.2, 0.02], [0.19, 0.015], [0.18, 0.01], [0.17, 0.005], [0.16, 0.0]],
         "g4": [[0.25, 0.06], [0.24, 0.05], [0.22, 0.05], [0.21, 0.04], [0.2, 0.04]]}
    r.update(kw)
    return r


LINES = {"g1": [0.1, 0.09], "g2": [0.5, 0.09], "g3": [0.1, 0.0], "g4": [0.09, 0.046]}
T3 = "{ic: 3, nd: 3, cd: 0.2}"


@unittest.skipUnless(NODE, "node not installed")
class DeepDiveNotes(unittest.TestCase):
    def notes(self, row, lists=None):
        return run_js(f"ddNotes({json.dumps(row)}, {json.dumps(LINES)}, {json.dumps(lists or {})}, {T3})")

    def test_dd_notes_strengths(self):
        n = self.notes(ddrow(), {"g1": "top", "g3": "upY"})
        look = " ".join(n["look"])
        self.assertIn("top-right of 4 of 4", look)
        self.assertIn("ROIC above the 9% cost of capital in all 5", look)
        self.assertIn("gross margin above a year earlier in each of the last 4 quarters", look)
        self.assertEqual(n["watch"], [])

    def test_dd_notes_watch_items(self):
        r = ddrow(it=False, ic=None, g1=[[0.2, 0.10], [0.2, 0.12], [0.2, 0.15], [0.2, 0.18], [0.2, 0.2]],
                  g2=[[None, None]] * 5)
        w = " ".join(self.notes(r)["watch"])
        self.assertIn("Interest cover not tested", w)
        self.assertIn("ROIC fell in", w)
        self.assertIn("Compounding Runway not shown", w)

    def test_dd_notes_failed_risk_check(self):
        w = " ".join(self.notes(ddrow(nd=4.5))["watch"])
        self.assertIn("Net debt ÷ EBITDA 4.5×", w)

    def test_dd_notes_empty_row(self):
        n = self.notes({})
        self.assertEqual(n["look"], [])
        self.assertTrue(any("Not enough data" in x for x in n["watch"]))


LS = """const mkLs = () => { const m = {}; return {getItem: k => k in m ? m[k] : null, setItem: (k, v) => { m[k] = String(v); }}; };"""
DB = """const mkDb = (failCode) => { const docs = {}, subs = []; let fail = failCode;
  const emit = () => subs.forEach(f => f({docs: Object.entries(docs).map(([id, v]) => ({id, exists: true, data: () => v}))}));
  const col = {onSnapshot: (f) => { subs.push(f); setTimeout(emit, 0); return () => {}; },
    doc: id => ({set: async v => { if (fail) throw {code: fail, message: "x"}; docs[id] = v; emit(); },
                 delete: async () => { delete docs[id]; emit(); }})};
  return {collection: () => col, setFail: c => { fail = c; }}; };"""
ENTRY = '{cik: 1, ticker: "AAA", priority: "A", note: "long thesis <b>x</b>", added: "2026-11-04", updated: "2026-11-04"}'


@unittest.skipUnless(NODE, "node not installed")
class WatchlistStore(unittest.TestCase):
    def test_store_local_fallback(self):
        got = run_js(f"""(async () => {{ {LS} const ls = mkLs();
          const a = makeWlStore({{use: async () => null, ls}}); const mode = await a.init(); await a.put({ENTRY});
          const b = makeWlStore({{use: async () => null, ls}}); await b.init();
          return [mode, b.all().map(e => e.note)]; }})()""")
        self.assertEqual(got, ["local", ["long thesis <b>x</b>"]])

    def test_store_db_put_and_remove(self):
        got = run_js(f"""(async () => {{ {DB} const db = mkDb();
          const s = makeWlStore({{use: async n => n === "db" ? db : null, ls: null}}); const mode = await s.init();
          const r = await s.put({ENTRY}); await new Promise(z => setTimeout(z, 5)); const n1 = s.all().length;
          await s.remove(1); await new Promise(z => setTimeout(z, 5)); return [mode, r.ok, n1, s.all().length]; }})()""")
        self.assertEqual(got, ["db", True, 1, 0])

    def test_store_write_refused_keeps_text(self):
        # an existing entry whose edit is refused keeps the edited text on screen (status shows "Not saved")
        got = run_js(f"""(async () => {{ {DB} const db = mkDb();
          const s = makeWlStore({{use: async n => n === "db" ? db : null, ls: null}}); await s.init();
          await s.put({ENTRY}); db.setFail("not_granted");
          const r = await s.put({{...{ENTRY}, note: "edited"}}); return [r.ok, r.code, s.get(1).note]; }})()""")
        self.assertEqual(got, [False, "not_granted", "edited"])

    def test_store_refused_add_rolls_back(self):
        got = run_js(f"""(async () => {{ {DB} const db = mkDb("not_granted");
          const s = makeWlStore({{use: async n => n === "db" ? db : null, ls: null}}); await s.init();
          const r = await s.put({ENTRY}, true); return [r.ok, s.has(1), s.readOnly()]; }})()""")
        self.assertEqual(got, [False, False, True])

    def test_store_mode_after_listener_error_still_writes(self):
        got = run_js("""(async () => { const docs = {}; const col = {onSnapshot: (f, err) => { setTimeout(() => err({code: "unavailable"}), 0); return () => {}; },
            doc: id => ({set: async v => { docs[id] = v; }, delete: async () => {}})};
          const s = makeWlStore({use: async () => ({collection: () => col}), ls: null}); await s.init(); await new Promise(z => setTimeout(z, 5));
          const r = await s.put({cik: 3, note: "n"}); return [s.mode(), r.ok, "3" in docs]; })()""")
        self.assertEqual(got, ["db-error", True, True])

    def test_store_none_when_storage_throws(self):
        got = run_js("""(async () => { const ls = {getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); }};
          const s = makeWlStore({use: async () => null, ls}); return await s.init(); })()""")
        self.assertEqual(got, "none")


def deck_input(**kw):
    G = [{"k": g, "n": f"Moat Screener {i + 1} · {n}", "q": "Question?", "xs": "X", "ys": "Y", "pts": g == "g3",
          "quads": ["Top-right", "TL", "BR", "BL"]} for i, (g, n) in enumerate([("g1", "Value Creation"), ("g2", "Compounding Runway"),
                                                                                ("g3", "Pricing Power"), ("g4", "Magic Formula")])]
    d = {"co": {"cik": 1, "ticker": "AAA", "name": "Acme & Sons", "sector": "Technology", "industry": "Software", "mcap": 5e10, "pe": 25.0, "ev_ebit": 20.0},
         "brief": {"desc": "Acme makes widgets.", "url": "https://www.sec.gov/x", "filed": "2026-02-01", "hq": "Austin, TX", "website": "acme.com",
                   "founded": {"year": 1990, "phrase": "founded in 1990"}, "fye": "Dec 31"},
         "scr": ddrow(), "q": {"end": ["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"], "revenue": [1e9, 1.1e9, 1.2e9, 1.3e9, 1.4e9],
                               "gross_margin": [0.5, 0.51, 0.52, 0.53, 0.54], "op_margin": [0.2, 0.21, 0.22, 0.23, 0.24], "fcf_margin": [0.1, 0.1, 0.1, 0.1, 0.1]},
         "entry": {"priority": "A", "note": "Durable franchise. Watch pricing.", "added": "2026-11-04"},
         "meta": {"sec_retrieved": "2026-11-03", "price_date": "2026-11-03"}, "lines": LINES, "groups": G,
         "pct": {"g1": 90, "g2": 80, "g3": 70, "g4": 60}, "lists": {"g1": "top"}, "medians": {"pe": 20.0, "ev_ebit": 15.0, "ey": 0.046},
         "risk": {"ic": "pass", "nd": "pass", "cd": "pass"}, "notes": {"look": ["In the top-right of 4 of 4."], "watch": ["ROIC fell."]}}
    for k, v in kw.items():
        d[k] = v
    return d


@unittest.skipUnless(NODE, "node not installed")
class Deck(unittest.TestCase):
    def deck(self, d):
        return run_js(f"buildDeck({json.dumps(d)})")

    def test_deck_five_slides_in_order(self):
        h = self.deck(deck_input())
        self.assertTrue(h.startswith("<!doctype html>"))
        self.assertEqual(h.count('<section class="slide'), 5)
        order = [h.index(t) for t in ("Investment snapshot", "Business overview", "Moat assessment", "Valuation and risk", "Analyst view and next steps")]
        self.assertEqual(order, sorted(order))
        self.assertIn("Acme &amp; Sons", h)
        self.assertEqual(h.count("not investment advice"), 5)
        self.assertIn("5/5", h)

    def test_deck_escapes_note(self):
        h = self.deck(deck_input(entry={"priority": "B", "note": "<script>alert(1)</script> & \"x\"", "added": "2026-11-04"}))
        self.assertNotIn("<script>alert(1)", h)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp;", h)

    def test_deck_missing_data(self):
        h = self.deck(deck_input(brief=None, q=None, scr={}, co={"cik": 2, "ticker": "ZZZ", "name": "Gone Inc"}, pct={}, lists={},
                                 risk={}, notes={"look": [], "watch": ["Not enough data in the filings to assess this company."]}))
        self.assertEqual(h.count('<section class="slide'), 5)
        self.assertIn("not available in filings", h)

    def test_deck_long_note_truncated(self):
        h = self.deck(deck_input(entry={"priority": "A", "note": "word " * 1000, "added": "2026-11-04"}))
        self.assertIn("continued in the dashboard", h)
        self.assertLess(h.count("word "), 450)  # ≈360 on slide 5 + the first-sentence thesis on slide 1, not 1,000

    def test_deck_no_external_scripts(self):
        h = self.deck(deck_input())
        self.assertNotIn("<script", h)
        links = re.findall(r'<link[^>]+href="([^"]+)"', h)
        self.assertTrue(all(u.startswith("https://fonts.") for u in links), links)


AUDIT = HTML.parent / "data" / "audit"
SITE = HTML.parent / "data" / "site_data.js"


def _load(p: Path, var: str) -> dict:
    return json.loads(p.read_text().split("=", 1)[1].rstrip().rstrip(";"))


BL = ["revenue", "gross_profit", "op_income", "one_offs", "clean_oi", "nopat", "da", "ebitda", "cfo", "interest",
      "equity", "cash", "excess_cash", "debt", "ic"]


def blk(**v):
    return [v.get(b) for b in BL]


@unittest.skipUnless(NODE and any(AUDIT.glob("a*.js")), "node or output/data/audit missing")
class CalcCheck(unittest.TestCase):
    """Deep-Dive calculation check (spec docs/specs/2026-11-04-calculation-check-design.md §2)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HTML.parent.parent / "src"))
        from mm_audit import load_export
        cls.A, cls.S = load_export(AUDIT), _load(SITE, "MM")

    def test_measures_match_screener_for_sample(self):
        import random
        random.seed(7)
        ciks = random.sample(sorted(self.A["co"]), 50) + ["1562088"]
        recs = {c: self.A["co"][c] for c in ciks}
        got = run_js(f"(() => {{ const R = {json.dumps(recs)}, B = {json.dumps(self.A['meta']['blocks'])}; "
                     f"const o = {{}}; for (const c in R) o[c] = auditMeasures(R[c], B).m; return o; }})()")
        bad = []
        for c in ciks:
            m, e = got[c], self.S["scr"]["co"][c]
            pairs = [("g1x", e["g1"][0][0]), ("g1y", e["g1"][0][1]), ("g2x", e["g2"][0][0]), ("g2y", e["g2"][0][1]),
                     ("g3y", e["g3"][0][1]), ("g4y", e["g4"][0][1]), ("ic", e["ic"]), ("nd", e["nd"]), ("cd", e["cd"])]
            for k, want in pairs:
                a = m[k]
                tol = 0.006 if k in ("ic", "nd") else 0.0006 if k == "cd" else max(1e-4, 1e-4 * abs(want or 0))
                if (a is None) != (want is None) or (a is not None and abs(a - want) > tol):
                    bad.append((c, k, a, want))
        self.assertEqual(bad, [])

    def test_na_rules(self):  # Review Focus 2: n/a exactly where the Screener has none
        r = {"pts": {"now": ["2026-06-30", True]}, "b": {"now": blk(revenue=100, gross_profit=50, clean_oi=-5, nopat=-4,
             ebitda=1, da=6, ic=-10, cash=5, debt=0)}, "m": {"ev": 0}}
        m = run_js(f"auditMeasures({json.dumps(r)}, {json.dumps(BL)}).m")
        self.assertEqual({k: m[k] for k in ("g1x", "g1y", "g2x", "g2y", "g3y", "g4y", "ic", "cd")},
                         {"g1x": None, "g1y": None, "g2x": None, "g2y": None, "g3y": None, "g4y": None, "ic": None, "cd": None})
        r["b"]["q12"] = blk(revenue=80, nopat=-9, ic=-10.5)  # capital grew 0.5 < 10% of |-10.5|: no return on new capital
        r["b"]["now"][BL.index("nopat")] = 3
        self.assertIsNone(run_js(f"auditMeasures({json.dumps(r)}, {json.dumps(BL)}).m.g2y"))

    def test_duol_rows(self):
        rows = run_js(f"ddCalcRows({json.dumps(self.A['co']['1562088'])}, {json.dumps(self.A['meta']['blocks'])}, "
                      f"{json.dumps(self.S['scr']['meta']['lines'])}, {{ic: 3, nd: 3, cd: 0.2}})")
        by = {r["k"]: r for r in rows}
        self.assertEqual(list(by), ["g1x", "g1y", "g2x", "g2y", "g3x", "g3y", "g4x", "g4y", "ic", "nd", "cd"])
        self.assertEqual(by["g1x"]["formula"], "(Revenue now ÷ revenue 12 quarters back)^(1/3) − 1")
        self.assertAlmostEqual(by["g1x"]["res"], 0.373, 3)
        self.assertEqual(by["g1x"]["side"], "Above")
        self.assertEqual([u[1] for u in by["g1x"]["used"]], [1145002000, 442389000])
        self.assertEqual(by["g4y"]["side"], "Below")
        self.assertEqual(by["ic"]["side"], "Pass: net cash, no interest expense filed")  # riskPass rule
        self.assertEqual(by["nd"]["side"], "Pass: net cash")
        self.assertEqual(by["cd"]["side"], "Pass: no debt")


def a1(ref: str):
    m = re.match(r"([A-Z]+)(\d+)$", ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + ord(ch) - 64
    return int(m.group(2)) - 1, col - 1


@unittest.skipUnless(NODE and any(AUDIT.glob("a*.js")), "node or output/data/audit missing")
class Workbook(unittest.TestCase):
    """The one-company workbook (spec §3): three tabs, every derived number a formula."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HTML.parent.parent / "src"))
        from mm_audit import load_export
        A, S = load_export(AUDIT), _load(SITE, "MM")
        cls.A, cls.S = A, S
        def wb(cik):
            return run_js(f"auditWorkbook({json.dumps(A['co'][cik])}, {json.dumps(A['meta'])}, {json.dumps(S['scr']['meta']['lines'])}, "
                          f"{{ic: 3, nd: 3, cd: 0.2}}, {json.dumps(S['scr']['co'][cik])}, {{ticker: {json.dumps(A['co'][cik]['t'])}, name: 'X', cik: {cik}}})")
        cls.duol, cls.evi = wb("1562088"), wb("65312")

    def sheet(self, wb, name):
        return next(s for s in wb["sheets"] if s["name"] == name)["rows"]

    def test_three_tabs_and_title(self):
        self.assertEqual([s["name"] for s in self.duol["sheets"]], ["Calculation check", "SEC inputs", "Sources"])
        self.assertEqual(self.duol["title"], "DUOL · Moat Momentum calculation check (data as of 2026-11-03)")

    def test_results_are_formulas(self):
        rows = self.sheet(self.duol, "Calculation check")
        res = [r for r in rows if r and r[0] and str(r[0].get("v", "")).startswith(("X · ", "Y · "))]
        self.assertEqual(len(res), 8)
        self.assertTrue(all("f" in r[1] for r in res))

    def test_formula_refs_exist(self):
        for wb in (self.duol, self.evi):
            sheets = {s["name"]: s["rows"] for s in wb["sheets"]}
            for name, rows in sheets.items():
                for r in rows:
                    for c in r or []:
                        if c and "f" in c:
                            for sh, ref in re.findall(r"(?:'([^']+)'!)?\$?([A-Z]{1,2}\$?\d+)", c["f"].replace("$", "")):
                                if c["f"].startswith("=HYPERLINK"):
                                    continue
                                i, j = a1(ref)
                                tgt = sheets[sh or name]
                                self.assertTrue(i < len(tgt) and tgt[i] and j < len(tgt[i]) and tgt[i][j] is not None,
                                                f"{name}: {c['f']} -> {sh or name}!{ref}")

    def test_signed_labels_are_text(self):
        rows = self.sheet(self.duol, "SEC inputs")
        labels = [r[0]["v"] for r in rows if r and r[0] and "v" in r[0]]
        self.assertIn("+ This year to date (10-Q)", labels)
        self.assertTrue(any(str(l).startswith("= ") for l in labels))
        self.assertFalse(any("f" in r[0] for r in rows if r and r[0]))

    def test_duol_inputs_and_pages(self):
        rows = self.sheet(self.duol, "SEC inputs")
        rev = [r for r in rows if r and r[0] and r[0].get("v") == "Last fiscal year (10-K)"][0]
        self.assertEqual([rev[2]["v"], rev[3]["v"], rev[4]["v"]], [1037589000, 748024000, 369495000])
        self.assertIn("F", rev[5]["v"])
        self.assertEqual(len(str(rev[6]["v"]).split(" · ")), 3)

    def test_every_company_sheet_matches_the_dashboard(self):  # spec §1 success: every result equals the dashboard
        src = HTML.read_text()
        ev = (HTML.parent.parent / "tests" / "js" / "xleval.js").resolve()
        code = "const MM = {}; const ok = v => v !== null && v !== undefined && isFinite(v);\n" + "".join(
            _fn(src, n) for n in ("riskPass", "auditMeasures", "ddCalcRows", "auditWorkbook",
                                                 "driveErrorText", "auditLinkState")) + f"""
const fs = require("fs"), vm = require("vm"), {{evalWorkbook}} = require({json.dumps(str(ev))});
const ctx = {{window: {{}}}}; vm.createContext(ctx);
for (const f of fs.readdirSync({json.dumps(str(AUDIT))}).filter(x => /^a\d+\.js$/.test(x))) vm.runInContext(fs.readFileSync({json.dumps(str(AUDIT))} + "/" + f, "utf8"), ctx);
vm.runInContext(fs.readFileSync({json.dumps(str(SITE))}, "utf8"), ctx);
const A = ctx.window.MM_AUDIT, S = ctx.window.MM.scr, bad = [], errs = []; let n = 0;
for (const cik in A.co) {{
  n++; const a = A.co[cik]; let out;
  try {{ out = evalWorkbook(auditWorkbook(a, A.meta, S.meta.lines, S.meta.defaults, S.co[cik], {{ticker: a.t, name: a.t, cik: +cik}})); }}
  catch (e) {{ errs.push([cik, String(e).slice(0, 160)]); continue; }}
  out["Calculation check"].forEach((r, i) => {{ if (r && r[3] === "No") bad.push([cik, a.t, r[0], r[1], r[2]]); }});
}}
console.log(JSON.stringify({{n, bad: bad.slice(0, 12), nbad: bad.length, errs: errs.slice(0, 5), nerr: errs.length}}));"""
        out = json.loads(subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True).stdout)
        self.assertGreater(out["n"], 1500)
        self.assertEqual((out["nerr"], out["errs"]), (0, []))
        self.maxDiff = None
        self.assertEqual((out["nbad"], out["bad"]), (0, []))

    def test_each_group_uses_its_own_line(self):  # review: Groups 3 and 4 X lines are set separately on the Screener
        ev = (HTML.parent.parent / "tests" / "js" / "xleval.js").resolve()
        L = dict(self.S["scr"]["meta"]["lines"]); L["g3"] = [0.2, L["g3"][1]]; L["g4"] = [0.5, L["g4"][1]]
        code = "const MM = {}; const ok = v => v !== null && v !== undefined && isFinite(v);\n" + "".join(
            _fn(HTML.read_text(), n) for n in ("riskPass", "auditMeasures", "ddCalcRows", "auditWorkbook")) + f"""
const {{evalWorkbook}} = require({json.dumps(str(ev))});
const wb = auditWorkbook({json.dumps(self.A['co']['1562088'])}, {json.dumps(self.A['meta'])}, {json.dumps(L)}, {{ic: 3, nd: 3, cd: 0.2}}, {json.dumps(self.S['scr']['co']['1562088'])}, {{ticker: "DUOL", cik: 1562088}});
const o = evalWorkbook(wb)["Calculation check"], rows = wb.sheets[0].rows, out = {{}}; let grp = "";
rows.forEach((r, i) => {{ const t = r && r[0] && r[0].v; if (r && r[0] && r[0].s === "sec") grp = t; if (typeof t === "string" && /^[XY] · /.test(t)) out[grp.slice(0, 7) + " " + t.slice(0, 1)] = o[i][4]; }});
console.log(JSON.stringify(out));"""
        lines = json.loads(subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(lines["Group 3 X"], 0.2)
        self.assertEqual(lines["Group 4 X"], 0.5)
        self.assertEqual(lines["Group 1 X"], L["g1"][0])

    def test_10k_point_single_line(self):  # Review Focus 1: EVI's points are 10-K years: no year-to-date rows
        labels = [r[0]["v"] for r in self.sheet(self.evi, "SEC inputs") if r and r[0] and "v" in r[0]]
        self.assertNotIn("+ This year to date (10-Q)", labels)
        self.assertIn("Fiscal year (10-K)", labels)


@unittest.skipUnless(NODE, "node not installed")
class DriveSheet(unittest.TestCase):
    """Create calculation sheet: connector failure messages and the remembered link (spec §4)."""

    def test_error_texts(self):  # Review Focus 5: each failure names its fix; nothing retries the write
        codes = ["server_not_connected", "selection_required", "needs_reauth", "approval_required", "not_in_manifest",
                 "not_granted", "capability_disabled", "capability_removed", "server_unavailable", "upstream_error",
                 "tool_error", "something_new"]
        got = run_js(f"{json.dumps(codes)}.map(c => driveErrorText(c))")
        by = dict(zip(codes, got))
        self.assertEqual(by["server_not_connected"]["msg"], "Add Google Drive in claude.ai Settings → Connectors, then try again.")
        self.assertEqual(by["selection_required"]["msg"], by["server_not_connected"]["msg"])
        self.assertEqual(by["needs_reauth"]["msg"], "Reconnect Google Drive in claude.ai Settings → Connectors, then try again.")
        self.assertEqual(by["approval_required"]["msg"], "Creating the sheet needs your approval; claude.ai asks when the dashboard is open there.")
        self.assertEqual(by["not_in_manifest"]["msg"], by["approval_required"]["msg"])
        self.assertEqual(by["not_granted"]["msg"], "Google Drive is not available in this view. Use Download as Excel.")
        for c in ("server_unavailable", "upstream_error", "tool_error", "something_new"):
            self.assertEqual(by[c]["msg"], "The sheet may have been created; check your Google Drive before trying again.")
        self.assertTrue(all(v["retry"] is False for v in got))

    def test_stale_link_offers_rebuild(self):
        st = run_js("[auditLinkState(null, '2026-11-03'), auditLinkState({url: 'u', built: '2026-11-03'}, '2026-11-03'), "
                    "auditLinkState({url: 'u', built: '2026-08-01'}, '2026-11-03'), auditLinkState({built: '2026-11-03'}, '2026-11-03')]")
        self.assertEqual(st, ["create", "open", "rebuild", "create"])


if __name__ == "__main__":
    unittest.main()
