"""Moat Momentum · invested-capital study (round 32, 2026-11-05): how the definition of invested capital (IC) changes
clean ROIC and the Screener lists. Asked by Jitti after comparing DUOL with GuruFocus (round 31).

Written down BEFORE running (variants, guard, pass rules), all results are reported:

Variants (12-month points of the Screener panel, as of 2026-11-03; NOPAT unchanged = clean OI × 0.79):
  A  current          equity + debt − (cash above 2% of revenue)
  A+G                 A, ROIC "not meaningful" when average IC < 10% of revenue (incl. negative)
  B  + op. leases     A + operating lease liability (total tag, else non-current + current)
  B+G                 B with the guard
  C  5% cash          equity + debt − (cash above 5% of revenue)
  D  WC cash          equity + debt − GuruFocus-style excess cash: cash − max(0, current liabilities − current
                      assets + cash)
  E  GF-like          total assets − (accounts payable and accrued) − D's excess cash (GuruFocus's formula from SEC
                      tags; FactSet maps lines differently, so it is close, not equal)
Only ROIC and IC change. EV, earnings yield and the risk checks stay as they are (leases in EV would also need lease
cost added back to EBITDA: out of scope).

Lists compared (raw 2×2 passes at the latest point, no risk filter, same lines as the page):
  M1 Value Creation  3-yr revenue growth ≥ 10% and ROIC ≥ 9%
  M2 Pricing Power   reinvestment ≥ 50% of NOPAT and return on added capital ≥ 9%
  M4 Magic Formula   ROIC ≥ median and earnings yield ≥ median (medians recomputed per variant)
  (M3 does not use invested capital.)

Pass rules, fixed in advance:
  1. Outliers: at most 2 companies with ROIC above 200% ("not meaningful" is allowed).
  2. Stability vs A: list overlap (Jaccard) ≥ 0.80 for M1, M2 and M4, and ROIC rank correlation (Spearman) ≥ 0.90.
  3. Collateral: the guard drops at most 5 companies from M1 or M4; every dropped name is listed and checked by hand.
  Adopt the simplest variant that meets 1–3. Leases (B) are adopted only if the companies whose ROIC falls most are
  mainly lease-heavy industries (retail, restaurants, transport, health-care services).

Run:  .venv/bin/python src/mm_extract.py extra   (once: the study-only balance tags)
      .venv/bin/python src/mm_ic_study.py
Out:  output/data/ic_study.json
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import mm_fundamentals as F

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"
AS_OF = "2026-11-03"
GUARD = 0.10      # average IC below 10% of revenue → ROIC not meaningful
HURDLE = 0.09
RAW = {"opl": ["OperatingLeaseLiability"], "opl_nc": ["OperatingLeaseLiabilityNoncurrent"],
       "opl_cur": ["OperatingLeaseLiabilityCurrent"], "ap_acc": ["AccountsPayableAndAccruedLiabilitiesCurrent"],
       "ap": ["AccountsPayableCurrent"], "accrued": ["AccruedLiabilitiesCurrent"]}

_orig_derive = F._derive


def _derive_with_raw(w: pd.DataFrame, tax_rate: float, excess_cash_pct: float) -> pd.DataFrame:
    """The model's _derive plus the raw tags this study needs (the model itself never reads them)."""
    d = _orig_derive(w, tax_rate, excess_cash_pct)
    extra = pd.DataFrame({k: F._first(w, tags) for k, tags in RAW.items()}, index=w.index).reset_index()
    return d.merge(extra, on=["cik", "end"], how="left")


def panel() -> pd.DataFrame:
    F._derive = _derive_with_raw
    try:
        from mm_quarterly import ttm_panel
        facts = pd.read_pickle(CACHE / "facts.pkl")
        extra = pd.read_pickle(CACHE / "extra_facts.pkl")  # study-only balances (mm_extract.py extra)
        facts = pd.concat([facts.astype({"tag": str, "kind": str, "form": str}),
                           extra.astype({"tag": str, "kind": str, "form": str})], ignore_index=True)
        p = ttm_panel(facts, AS_OF, 0.21, 0.02)
    finally:
        F._derive = _orig_derive
    return p[p["filed"] <= pd.Timestamp(AS_OF)].sort_values(["cik", "end"]).reset_index(drop=True)


def site() -> tuple[dict, dict]:
    s = (ROOT / "output" / "data" / "site_data.js").read_text()
    j = json.loads(s[s.index("{"):].rstrip().rstrip(";"))
    return j["scr"]["co"], {c["cik"]: c for c in j["companies"]}


def variants(p: pd.DataFrame) -> dict[str, tuple[pd.Series, bool]]:
    rev, cash = p["revenue"], p["cash"].fillna(0)
    base = p["equity"] + p["debt"].fillna(0)
    opl = p["opl"].fillna(F._sum_any(p["opl_nc"], p["opl_cur"])).fillna(0)
    excess_d = (cash - (p["liab_cur"] - p["assets_cur"] + cash).clip(lower=0)).clip(lower=0)
    ap = p["ap_acc"].fillna(F._sum_any(p["ap"], p["accrued"])).fillna(0)
    a = base - (cash - 0.02 * rev).clip(lower=0)
    return {"A": (a, False), "A+G": (a, True), "B": (a + opl, False), "B+G": (a + opl, True),
            "C": (base - (cash - 0.05 * rev).clip(lower=0), False), "D": (base - excess_d, False),
            "E": (p["assets"] - ap - excess_d, False)}


def run_variant(p: pd.DataFrame, ic: pd.Series, guard: bool, ey_now: pd.Series, a: pd.Timestamp) -> pd.DataFrame:
    from mm_quarterly import lag_q
    from mm_screener import group_series
    q = p.copy()
    q["ic"] = ic
    avg = pd.concat([ic, lag_q(q, "ic", 4)], axis=1).mean(axis=1)
    ok = avg > 0
    if guard:
        ok &= avg >= GUARD * q["revenue"]
    q["roic_ttm"] = (q["nopat"] / avg).where(ok)
    q["ic_avg"] = avg
    g = group_series(q)
    latest = g[g["end"] >= a - pd.Timedelta(days=548)].sort_values("end").drop_duplicates("cik", keep="last")
    latest = latest.set_index("cik")
    latest["g4y"] = ey_now.reindex(latest.index)
    return latest


def passes(t: pd.DataFrame) -> dict[str, set]:
    both = t[["g4x", "g4y"]].dropna()
    mx, my = both["g4x"].median(), both["g4y"].median()
    return {"M1": set(t.index[(t["g1x"] >= 0.10) & (t["g1y"] >= HURDLE)]),
            "M2": set(t.index[(t["g2x"] >= 0.50) & (t["g2y"] >= HURDLE)]),
            "M4": set(t.index[(t["g4x"] >= mx) & (t["g4y"] >= my)]), "_med": (mx, my)}


def main() -> None:
    a = pd.Timestamp(AS_OF)
    scr, comp = site()
    uni = {int(k) for k in scr}
    tick = {int(k): (comp.get(int(k)) or {}).get("ticker", str(k)) for k in scr}
    sicd = {int(k): (comp.get(int(k)) or {}).get("sic_desc", "") for k in scr}
    ey = pd.Series({int(k): v["g4"][0][1] for k, v in scr.items() if v.get("g4")}, dtype=float)
    p = panel()
    p = p[p["cik"].isin(uni)].reset_index(drop=True)
    names = lambda s: sorted(tick[c] for c in s)  # noqa: E731

    res, lists, tabs = {}, {}, {}
    for name, (ic, guard) in variants(p).items():
        t = run_variant(p, ic, guard, ey, a)
        tabs[name], lists[name] = t, passes(t)

    # check: variant A reproduces the published Screener lists
    pub = {"M1": "g1", "M2": "g2", "M4": "g4"}
    ref = {}
    for m, g in pub.items():
        lx, ly = ((0.10, HURDLE) if g == "g1" else (0.50, HURDLE) if g == "g2" else lists["A"]["_med"])
        ref[m] = {int(k) for k, v in scr.items() if v.get(g) and None not in v[g][0] and v[g][0][0] >= lx and v[g][0][1] >= ly}
    check = {m: {"published": len(ref[m]), "variant_A": len(lists["A"][m]), "same": ref[m] == lists["A"][m]} for m in pub}

    A = tabs["A"]
    for name, t in tabs.items():
        r = t["g1y"]
        common = r.dropna().index.intersection(A["g1y"].dropna().index)
        rho = r[common].rank().corr(A["g1y"][common].rank())
        dropped_guard = {m: names(lists["A"][m] - lists[name][m]) for m in ("M1", "M4")} if name.endswith("+G") else None
        fall = ((A["g1y"] - r) / A["g1y"].abs()).where(A["g1y"].abs() > 0)
        movers = fall[fall > 1 / 3].index
        top_ind = pd.Series([sicd[c] for c in movers]).value_counts().head(8).to_dict() if len(movers) else {}
        res[name] = {
            "roic_over_200": int((r > 2).sum()), "roic_over_100": int((r > 1).sum()),
            "roic_missing": int(r.isna().sum()), "median_roic": round(float(r.median()), 4),
            "spearman_vs_A": round(float(rho), 4),
            "lists": {m: {"n": len(lists[name][m]),
                          "jaccard_vs_A": round(len(lists[name][m] & lists["A"][m]) / max(1, len(lists[name][m] | lists["A"][m])), 3),
                          "added": names(lists[name][m] - lists["A"][m]), "dropped": names(lists["A"][m] - lists[name][m])}
                      for m in ("M1", "M2", "M4")},
            "medians_M4": [round(float(x), 4) for x in lists[name]["_med"]],
            "top_roic": [[tick[c], round(float(v), 2)] for c, v in r.dropna().sort_values(ascending=False).head(10).items()],
            "roic_fell_by_a_third": {"n": int(len(movers)), "industries": top_ind},
            "guard_dropped": dropped_guard,
            "DUOL": None if 1562088 not in t.index else round(float(t.loc[1562088, "g1y"]), 4) if pd.notna(t.loc[1562088, "g1y"]) else "n.m.",
        }
    # companies with negative equity (buybacks or accumulated losses): where do they land?
    neg = A.index[A["equity"] < 0]
    res["_negative_equity"] = {"n": int(len(neg)), "names": names(neg)[:40],
                               "in_M1_or_M4_A": names(set(neg) & (lists["A"]["M1"] | lists["A"]["M4"])),
                               "in_M1_or_M4_A+G": names(set(neg) & (lists["A+G"]["M1"] | lists["A+G"]["M4"]))}
    # lease coverage in the universe at the latest point
    opl = A["opl"].fillna(F._sum_any(A["opl_nc"], A["opl_cur"]))
    res["_coverage"] = {"companies": int(len(A)), "op_lease_filed": int(opl.notna().sum()),
                        "op_lease_from_split_tags_only": int((A["opl"].isna() & opl.notna()).sum()),
                        "payables_filed": int(A["ap_acc"].fillna(F._sum_any(A["ap"], A["accrued"])).notna().sum())}
    out = {"as_of": AS_OF, "guard": GUARD, "check_variant_A_equals_published": check, "variants": res}
    (ROOT / "output" / "data" / "ic_study.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(check))
    for name, v in res.items():
        if name.startswith("_"):
            continue
        L = v["lists"]
        print(f"{name:4s} >200%:{v['roic_over_200']:3d} >100%:{v['roic_over_100']:3d} missing:{v['roic_missing']:4d} "
              f"med:{v['median_roic']:.3f} rho:{v['spearman_vs_A']:.3f} | "
              + " ".join(f"{m} {L[m]['n']} J{L[m]['jaccard_vs_A']}" for m in L) + f" | DUOL {v['DUOL']}")
    print(json.dumps({k: res[k] for k in ("_negative_equity", "_coverage")}, indent=1))


if __name__ == "__main__":
    main()
