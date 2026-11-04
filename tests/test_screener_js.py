"""Screener page logic (riskPass, groupLists, overlap) run in Node, extracted from output/moat_momentum.html.
Spec docs/specs/2026-11-04-screener-design.md §4–6. Skipped when Node is not installed."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
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
    code = pre + "".join(_fn(src, n) for n in ("pctRanks", "groupLists", "overlap", "riskPass")) + \
        f"\nconsole.log(JSON.stringify({expr}));"
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


if __name__ == "__main__":
    unittest.main()
