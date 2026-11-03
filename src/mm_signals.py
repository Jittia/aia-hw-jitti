"""Moat Momentum v2.0 · the 10 signals at one screen date (spec docs/specs/2026-11-03-compounder-signal-design.md §4).

raw_signals(panel)   signals that need only the company's own history, on every row of a ttm_panel
signals_at(...)      universe B at the screen (from the v1.1 engine: universe, risk gate, context Moat Score), the
                     company's latest 12-month point filed by then, the peer-relative signals, and 0–100 ranks within
                     the industry peer group (r_<name>; higher raw value = higher rank, direction applied later).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mm_fundamentals import scoring_table
from mm_quarterly import lag_q, ttm_panel
from mm_score import rank_in_groups, score_as_of

# name, expected direction (+1 higher is better; 0 = decided in training, spec §5)
SIGNALS = [
    ("s01_roic_chg", 1), ("s02_incr_roic", 1), ("s03_gm_chg", 1), ("s04_gm_accel", 1), ("s05_om_chg", 1),
    ("s08_rev_excess", 1), ("s09_rev_accel", 1), ("s10_peer_rank_chg", 1), ("s11_fcf_margin_chg", 1),
    ("s14_roic_rank", 0),
]
PEER_METRICS = ["roic_ttm", "gross_margin", "op_margin", "asset_turnover"]


def _finite(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    return s.where(np.isfinite(s))


def raw_signals(p: pd.DataFrame) -> pd.DataFrame:
    p = p.sort_values(["cik", "end"]).reset_index(drop=True).copy()
    L = lambda col, n: lag_q(p, col, n)  # noqa: E731
    p["s01_roic_chg"] = _finite(p["roic_ttm"] - L("roic_ttm", 4))
    d_nopat, ic4 = p["nopat"] - L("nopat", 4), L("ic", 4)
    d_ic = p["ic"] - ic4
    grew = (d_ic > 0) & (d_ic >= 0.10 * ic4.abs())  # same rule as v1.x incremental ROIC
    p["s02_incr_roic"] = _finite(d_nopat / d_ic.where(grew)).clip(-1, 2)
    p["s03_gm_chg"] = _finite(p["q_gross_margin"] - L("q_gross_margin", 4))
    p["s04_gm_accel"] = _finite(p["s03_gm_chg"] - L("s03_gm_chg", 2))
    p["s05_om_chg"] = _finite(p["q_op_margin"] - L("q_op_margin", 4))
    base = L("q_revenue", 4)
    p["rev_growth"] = _finite(p["q_revenue"] / base.where(base > 0) - 1)
    p["s09_rev_accel"] = _finite(p["rev_growth"] - L("rev_growth", 2))
    p["s11_fcf_margin_chg"] = _finite(p["fcf_margin"] - L("fcf_margin", 4))
    if "revenue" in p:
        peak = pd.concat([L("revenue", k) for k in range(1, 9)], axis=1).max(axis=1)
        p["rebound"] = p["revenue"] < 0.8 * peak  # recovering toward an earlier level (spec: rebound check, 2026-11-03)
    for m in PEER_METRICS:
        if m in p:
            p[f"{m}_lag4"] = L(m, 4)
    return p


def _group_pct(df: pd.DataFrame, cols: list[str], group: pd.Series) -> pd.DataFrame:
    return df[cols].groupby(group).rank(pct=True) * 100


def signals_at(facts: pd.DataFrame, companies: pd.DataFrame, screen: str, settings: dict, live: bool,
               panel: pd.DataFrame | None = None) -> pd.DataFrame:
    tax, cash = settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"]
    res = score_as_of(scoring_table(facts, screen, tax, cash, ttm=False), companies, screen, settings, live)["results"]
    u = res[res["in_universe"]][["cik", "ticker", "name", "sic", "industry_group", "moat_score", "rank",
                                 "gate_removed", "gate_flags", "gate_reasons"]].rename(columns={"rank": "moat_rank"})
    p = raw_signals(ttm_panel(facts, screen, tax, cash) if panel is None else panel)
    a = pd.Timestamp(screen)
    p = p[(p["filed"] <= a) & (p["end"] >= a - pd.Timedelta(days=548))]
    latest = p.sort_values("end").drop_duplicates("cik", keep="last")
    keep = ["cik", "end", "filed", "accn", "is_ttm", "revenue", "rev_growth", "rebound"] + [n for n, _ in SIGNALS if n in p] \
        + PEER_METRICS + [f"{m}_lag4" for m in PEER_METRICS]
    x = u.merge(latest[keep], on="cik", how="left").reset_index(drop=True)
    g = x["industry_group"]
    x["s08_rev_excess"] = x["rev_growth"] - x.groupby("industry_group")["rev_growth"].transform("median")
    now = _group_pct(x, PEER_METRICS, g).mean(axis=1)
    old = _group_pct(x, [f"{m}_lag4" for m in PEER_METRICS], g).mean(axis=1)
    x["s10_peer_rank_chg"] = now - old
    x["s14_roic_rank"] = _group_pct(x, ["roic_ttm"], g)["roic_ttm"]
    names = [n for n, _ in SIGNALS]
    x[names] = x[names].apply(_finite)
    ranks = rank_in_groups(x[names], g, x["sic"])
    for n in names:
        x[f"r_{n}"] = ranks[n].astype(float)
    x["screen"] = screen
    return x
