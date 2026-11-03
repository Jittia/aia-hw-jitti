"""Moat Momentum v2.0 · winner label: did the company become a "moat compounder" in the next 12 quarters?
(spec docs/specs/2026-11-03-compounder-signal-design.md §2)

label(panel_all, rows) reads 12-month points at the screen point (+0) and +4, +8, +12 quarters later from a ttm_panel
built with all filings, and checks all six conditions:
  c1_cagr      revenue CAGR ≥ 20% a year
  c2_peers     CAGR at least 10 points above the median of the same industry group at that screen
  c3_steady    revenue up at +4, +8 and +12 versus the point before
  c4_roic      clean ROIC > 9% at ≥ 2 of +4/+8/+12, and ROIC(+12) ≥ ROIC(0) − 2 points
  c5_margin    gross margin(+12) ≥ gross margin(0) − 2 points (passes when gross margin is not reported)
  c6_organic   goodwill added ÷ starting assets < 25%
Missing data → winner = NaN ("no outcome"), never False: no revenue at +0, +4, +8 or +12 (acquired, delisted,
stopped filing, or an untagged 10-Q), or clean ROIC missing at more than one of +4/+8/+12 (fixed 2026-11-04 after review).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CAGR_MIN, PEER_EXCESS, HURDLE, ROIC_SLACK, GM_SLACK, GOODWILL_MAX = 0.20, 0.10, 0.09, 0.02, 0.02, 0.25
COLS = ["revenue", "roic_ttm", "gross_margin", "goodwill", "assets"]


def _at(panel: pd.DataFrame, rows: pd.DataFrame, quarters: int) -> pd.DataFrame:
    """Values of COLS for each row's company at the period ending `quarters` later (±20 days)."""
    left = pd.DataFrame({"cik": rows["cik"].to_numpy(), "pos": np.arange(len(rows)),
                         "target": (pd.to_datetime(rows["end"]) + pd.DateOffset(months=3 * quarters)).astype("datetime64[ns]").to_numpy()})
    right = panel[["cik", "end"] + COLS].rename(columns={"end": "target"})
    right["target"] = right["target"].astype("datetime64[ns]")
    right = right.sort_values("target")
    m = pd.merge_asof(left.sort_values("target"), right, on="target", by="cik", direction="nearest",
                      tolerance=pd.Timedelta(days=20))
    return m.sort_values("pos")[COLS].reset_index(drop=True)


def label(panel_all: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    p = panel_all.copy()
    for c in COLS:
        if c not in p:
            p[c] = np.nan
    v = {q: _at(p, rows, q) for q in (0, 4, 8, 12)}
    r0, r12 = v[0]["revenue"], v[12]["revenue"]
    out = pd.DataFrame({"cik": rows["cik"].to_numpy(), "end": pd.to_datetime(rows["end"]).to_numpy()})
    cagr = (r12 / r0.where(r0 > 0)) ** (1 / 3) - 1
    out["cagr3"] = cagr.where(np.isfinite(cagr))
    peer_med = out["cagr3"].groupby(rows["industry_group"].to_numpy()).transform("median")
    out["c1_cagr"] = out["cagr3"] >= CAGR_MIN
    out["c2_peers"] = (out["cagr3"] - peer_med) >= PEER_EXCESS
    out["c3_steady"] = (v[4]["revenue"] > r0) & (v[8]["revenue"] > v[4]["revenue"]) & (r12 > v[8]["revenue"])
    above = sum((v[q]["roic_ttm"] > HURDLE).astype(int) for q in (4, 8, 12))
    out["c4_roic"] = (above >= 2) & (v[12]["roic_ttm"] >= v[0]["roic_ttm"] - ROIC_SLACK)
    g0, g12 = v[0]["gross_margin"], v[12]["gross_margin"]
    out["c5_margin"] = (g12 >= g0 - GM_SLACK) | g0.isna() | g12.isna()
    added = v[12]["goodwill"].fillna(0) - v[0]["goodwill"].fillna(0)
    out["c6_organic"] = (added / v[0]["assets"].where(v[0]["assets"] > 0)).fillna(0) < GOODWILL_MAX
    conds = ["c1_cagr", "c2_peers", "c3_steady", "c4_roic", "c5_margin", "c6_organic"]
    win = out[conds].all(axis=1)
    have = r0.notna() & v[4]["revenue"].notna() & v[8]["revenue"].notna() & r12.notna()
    have &= sum(v[q]["roic_ttm"].isna().astype(int) for q in (4, 8, 12)) <= 1
    out["winner"] = win.astype(object).where(have, np.nan)
    return out
